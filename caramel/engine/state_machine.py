"""
Core State Machine Orchestrator for Project Caramel / Uranus.
Coordinates Audio Streaming, Silero VAD, Vosk ASR, Trie Matching, and Subprocess Execution.
Enforces the 3 primary states: DORMANT -> LISTENING_COMMAND -> PROCESSING_AND_EXECUTION.
"""

import collections
from enum import Enum
import threading
import time
from typing import Callable, Deque, List, Optional

import numpy as np

from caramel.audio.vad import EndOfUtteranceDetector, SileroVAD, SpeechState
from caramel.engine.registry import CommandRegistry
from caramel.engine.search import parse_search_query, create_search_command
from caramel.engine.trie import MatchResult
from caramel.executor.launcher import ApplicationLauncher, ExecutionResult
from caramel.recognizer.vosk_engine import VoskRecognizerEngine
from caramel.utils.profiler import CommandMetrics
from config.settings import CommandDefinition, config


class AgentState(Enum):
    DORMANT = "DORMANT"
    LISTENING_COMMAND = "LISTENING_COMMAND"
    PROCESSING_AND_EXECUTION = "PROCESSING_AND_EXECUTION"


class CaramelStateMachine:
    """
    Central coordinator of the Caramel voice agent.
    Manages deterministic state transitions, pre-roll & hangover audio buffering,
    one-breath and two-breath speech lifecycles, and safe command execution.
    """
    # Pre-roll chunks kept during DORMANT silence (~192ms @ 32ms/chunk) so unvoiced
    # initial consonants (e.g. /k/ in 'Caramel') are never clipped before VAD triggers.
    PREROLL_CHUNKS = 6
    # Hangover chunks fed to ASR after speech ceases in DORMANT (~384ms) so Kaldi
    # has sufficient trailing acoustic context to commit the wake word.
    DORMANT_HANGOVER_CHUNKS = 12

    def __init__(
        self,
        vad: Optional[SileroVAD] = None,
        eou_detector: Optional[EndOfUtteranceDetector] = None,
        recognizer: Optional[VoskRecognizerEngine] = None,
        registry: Optional[CommandRegistry] = None,
        launcher: Optional[ApplicationLauncher] = None,
        dry_run: bool = False,
        wake_word: Optional[str] = None
    ):
        self.vad = vad or SileroVAD()
        self.eou_detector = eou_detector or EndOfUtteranceDetector()
        self.recognizer = recognizer or VoskRecognizerEngine()
        self.registry = registry or CommandRegistry()
        self.launcher = launcher or ApplicationLauncher(dry_run=dry_run)

        self.current_state = AgentState.DORMANT
        self._custom_wake_word = wake_word.strip().lower() if wake_word else None
        if (
            self._custom_wake_word
            and hasattr(self.recognizer, "grammar_list")
            and self._custom_wake_word not in self.recognizer.grammar_list
        ):
            updated_grammar = [self._custom_wake_word] + [
                g for g in self.recognizer.grammar_list if g != config.wake_word
            ]
            self.recognizer.update_grammar(updated_grammar)

        # Pre-roll and hangover state for DORMANT wake-word spotting
        self._preroll_buffer: Deque[np.ndarray] = collections.deque(maxlen=self.PREROLL_CHUNKS)
        self._dormant_hangover: int = 0
        self._dormant_dirty: bool = False

        # Post-wake-word command speech tracking (supports both one-breath and two-breath commands)
        self._command_speech_started: bool = False
        self._post_wake_silence_seen: bool = False
        self._command_audio_chunks: List[np.ndarray] = []

        # Timing and latency metrics
        self.wake_detected_time: float = 0.0
        self.eou_detected_time: float = 0.0
        self.last_execution_result: Optional[ExecutionResult] = None
        self.last_metrics: Optional[CommandMetrics] = None
        self._current_metrics: CommandMetrics = CommandMetrics()

        # Observer callbacks
        self.on_state_change: Optional[Callable[[AgentState, AgentState], None]] = None
        self.on_wake_detected: Optional[Callable[[], None]] = None
        self.on_command_matched: Optional[Callable[[CommandDefinition, str], None]] = None
        self.on_command_executed: Optional[Callable[[ExecutionResult], None]] = None
        self.on_command_rejected: Optional[Callable[[str, str], None]] = None

        self._lock: threading.RLock = threading.RLock()

    @property
    def wake_word(self) -> str:
        """Active wake word derived from configuration or explicit override."""
        return self._custom_wake_word or config.wake_word

    def _transition(self, new_state: AgentState) -> None:
        """Atomic state transition."""
        if self.current_state != new_state:
            old_state = self.current_state
            self.current_state = new_state
            if self.on_state_change:
                self.on_state_change(old_state, new_state)

    def cancel(self) -> None:
        """Emergency cancellation: immediately resets all states and returns to DORMANT."""
        with self._lock:
            self._finalize_and_return_dormant()

    def _extract_post_wake_words(self, text: str) -> List[str]:
        """
        Extracts words spoken after the wake word (if present), or all words
        if the wake word was already consumed.
        Example:
            '[unk] caramel open brave' -> ['open', 'brave']
            'caramel open anti gravity' -> ['open', 'anti', 'gravity']
            'open brave' -> ['open', 'brave']
            'caramel' -> []
        """
        words = text.strip().lower().split()
        ww = self.wake_word
        if ww in words:
            idx = len(words) - 1 - words[::-1].index(ww)
            return words[idx + 1:]
        return words

    def _clean_spoken_text(self, text: str) -> str:
        """Returns normalized command string stripped of leading wake word."""
        return " ".join(self._extract_post_wake_words(text)).strip()

    def _enter_listening_mode(self, current_text: str, is_speech: bool, prob: float) -> None:
        """Transitions from DORMANT to LISTENING_COMMAND without losing active speech frames."""
        now = time.perf_counter()
        self.wake_detected_time = now
        self._current_metrics = CommandMetrics(wake_detected_time=now)

        if self.on_wake_detected:
            self.on_wake_detected()

        self.eou_detector.reset()
        self._preroll_buffer.clear()
        self._dormant_hangover = 0
        self._command_audio_chunks.clear()

        post_wake_words = self._extract_post_wake_words(current_text)
        # Only start open-vocabulary decoding when a dynamic search command is detected,
        # avoiding unnecessary full-graph decoding overhead on standard commands.
        if "search" in post_wake_words:
            self.recognizer.start_open_decoding()
        else:
            self.recognizer.stop_open_decoding()

        self._command_speech_started = len(post_wake_words) > 0
        self._post_wake_silence_seen = not is_speech

        if self._command_speech_started:
            self._current_metrics.speech_start_time = now
            self.eou_detector.process_vad_result(True, prob)

        self._transition(AgentState.LISTENING_COMMAND)

    def process_chunk(self, chunk: np.ndarray) -> AgentState:
        """
        Process a single 512-sample (32ms) audio chunk through the active state.
        Returns the agent's state after processing.
        """
        with self._lock:
            # 1. STATE: DORMANT
            if self.current_state == AgentState.DORMANT:
                is_speech, prob = self.vad.is_speech(chunk)

                if is_speech:
                    # Flush pre-roll buffer on speech onset so initial consonants are preserved
                    if self._dormant_hangover == 0 and self._preroll_buffer:
                        for pre_chunk in self._preroll_buffer:
                            self.recognizer.feed_chunk(pre_chunk, include_partial=False)
                        self._preroll_buffer.clear()

                    self._dormant_hangover = self.DORMANT_HANGOVER_CHUNKS
                    self._dormant_dirty = True

                    is_final, text = self.recognizer.feed_chunk(chunk, include_partial=True)
                    if self.wake_word in text.lower().split():
                        self._enter_listening_mode(text, is_speech=True, prob=prob)

                else:
                    if self._dormant_hangover > 0:
                        self._dormant_hangover -= 1
                        is_final, text = self.recognizer.feed_chunk(chunk, include_partial=True)
                        if self.wake_word in text.lower().split():
                            self._enter_listening_mode(text, is_speech=False, prob=prob)
                        elif self._dormant_hangover == 0 and self._dormant_dirty:
                            # Speech ended in DORMANT without wake word; reset lattice cleanly
                            self.recognizer.reset()
                            self._dormant_dirty = False
                    else:
                        if self._dormant_dirty:
                            self.recognizer.reset()
                            self._dormant_dirty = False
                        self._preroll_buffer.append(chunk)

                return self.current_state

            # 2. STATE: LISTENING_COMMAND
            elif self.current_state == AgentState.LISTENING_COMMAND:
                self._command_audio_chunks.append(chunk)
                is_speech, prob = self.vad.is_speech(chunk)
                _, current_text = self.recognizer.feed_chunk(chunk, include_partial=True)

                post_words = self._extract_post_wake_words(current_text)
                if not getattr(self.recognizer, "is_open_decoding", False) and "search" in post_words:
                    self.recognizer.start_open_decoding()
                    if hasattr(self.recognizer, "feed_open_chunks"):
                        self.recognizer.feed_open_chunks(self._command_audio_chunks)

                # Determine whether post-wake-word command speech has started
                if not self._command_speech_started:
                    if len(post_words) > 0:
                        self._command_speech_started = True
                        self._current_metrics.speech_start_time = time.perf_counter()
                    elif not is_speech:
                        self._post_wake_silence_seen = True
                    elif is_speech and self._post_wake_silence_seen:
                        self._command_speech_started = True
                        self._current_metrics.speech_start_time = time.perf_counter()

                # Feed VAD into EOU detector:
                # Only count speech/EOU once post-wake-word command speech has started;
                # otherwise count towards the 5.0s speech-start timeout.
                effective_speech = is_speech if self._command_speech_started else False
                speech_state, _ = self.eou_detector.process_vad_result(effective_speech, prob)

                if speech_state == SpeechState.TIMEOUT_TRIGGERED:
                    if self.on_command_rejected:
                        self.on_command_rejected("Speech start timeout (5.0s elapsed)", "")
                    self._finalize_and_return_dormant()
                    return self.current_state

                if speech_state in (SpeechState.EOU_TRIGGERED, SpeechState.MAX_DURATION_EXCEEDED):
                    now = time.perf_counter()
                    self.eou_detected_time = now
                    self._current_metrics.eou_detected_time = now
                    self._transition(AgentState.PROCESSING_AND_EXECUTION)
                    self._process_and_execute()
                    return self.current_state

                return self.current_state

            # 3. STATE: PROCESSING_AND_EXECUTION
            elif self.current_state == AgentState.PROCESSING_AND_EXECUTION:
                return self.current_state

        return self.current_state

    def _process_and_execute(self) -> None:
        """
        Finalizes Vosk speech recognition, evaluates text against Trie,
        and dispatches valid commands.
        Always returns to DORMANT.
        """
        raw_text = self.recognizer.get_final_result()
        open_text = self.recognizer.get_open_final_result()
        cleaned_text = self._clean_spoken_text(raw_text)
        cleaned_open_text = self._clean_spoken_text(open_text)

        if not cleaned_text and not cleaned_open_text:
            if self.on_command_rejected:
                self.on_command_rejected("Empty speech or silence", raw_text)
            self._finalize_and_return_dormant()
            return

        # 1. Check dynamic search intent
        is_search_intent = (
            cleaned_text.startswith("search")
            or cleaned_open_text.startswith("search")
            or "search" in cleaned_text.split()[:2]
            or "search" in cleaned_open_text.split()[:2]
        )

        if is_search_intent:
            search_res = None
            text_to_parse = ""

            if cleaned_open_text:
                candidate_text = cleaned_open_text if cleaned_open_text.startswith("search") else f"search {cleaned_open_text}"
                search_res = parse_search_query(candidate_text)
                if search_res:
                    text_to_parse = candidate_text

            # If search_res not yet parsed or missing query terms, retry on buffered waveform
            if search_res is None and self._command_audio_chunks:
                try:
                    pcm_bytes = np.concatenate(self._command_audio_chunks).tobytes()
                    direct_open = self.recognizer.transcribe_open_waveform(pcm_bytes)
                    cleaned_direct = self._clean_spoken_text(direct_open)
                    if cleaned_direct:
                        candidate_text = cleaned_direct if cleaned_direct.startswith("search") else f"search {cleaned_direct}"
                        search_res = parse_search_query(candidate_text)
                        if search_res:
                            text_to_parse = candidate_text
                except Exception:
                    pass

            if search_res is None and cleaned_text:
                search_res = parse_search_query(cleaned_text)
                if search_res:
                    text_to_parse = cleaned_text

            if search_res is not None:
                command = create_search_command(search_res, phrase=text_to_parse)
                self._current_metrics.match_completed_time = time.perf_counter()
                if self.on_command_matched:
                    self.on_command_matched(command, text_to_parse)

                exec_result = self.launcher.execute(command)
                self._current_metrics.execution_completed_time = time.perf_counter()
                self.last_execution_result = exec_result
                self.last_metrics = self._current_metrics
                if self.on_command_executed:
                    self.on_command_executed(exec_result)

                self._finalize_and_return_dormant()
                return

        # 2. Query deterministic Trie
        match_result, command = self.registry.evaluate(cleaned_text)
        self._current_metrics.match_completed_time = time.perf_counter()

        if match_result == MatchResult.EXACT_MATCH and command is not None:
            if self.on_command_matched:
                self.on_command_matched(command, cleaned_text)

            # Safe detached execution
            exec_result = self.launcher.execute(command)
            self._current_metrics.execution_completed_time = time.perf_counter()
            self.last_execution_result = exec_result
            self.last_metrics = self._current_metrics

            if self.on_command_executed:
                self.on_command_executed(exec_result)

        elif match_result == MatchResult.PREFIX_ONLY:
            if self.on_command_rejected:
                self.on_command_rejected("Incomplete command prefix", cleaned_text)
        else:
            if self.on_command_rejected:
                self.on_command_rejected("Unknown or unregistered command", cleaned_text)

        self._finalize_and_return_dormant()

    def _finalize_and_return_dormant(self) -> None:
        """Clean all component states and return agent to DORMANT."""
        self.vad.reset()
        self.eou_detector.reset()
        self.recognizer.reset()
        self.recognizer.stop_open_decoding()
        self._preroll_buffer.clear()
        self._command_audio_chunks.clear()
        self._dormant_hangover = 0
        self._dormant_dirty = False
        self._command_speech_started = False
        self._post_wake_silence_seen = False
        self._transition(AgentState.DORMANT)
