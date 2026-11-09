"""
Vosk Streaming Speech Recognition Engine with Dynamic Constrained Grammar.
Provides real-time Kaldi-based audio decoding restricted strictly to registered commands,
the configured wake word, and '[unk]'.
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import vosk

from config.settings import config


class VoskRecognizerEngine:
    """
    Offline streaming ASR wrapper around Vosk / Kaldi.
    Enforces a strict grammar FST so the engine cannot hallucinate words outside
    the registered vocabulary.
    """
    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        sample_rate: Optional[int] = None,
        custom_grammar: Optional[List[str]] = None
    ):
        self.model_path = Path(model_path or config.VOSK_MODEL_PATH)
        if not self.model_path.is_dir():
            raise FileNotFoundError(f"Vosk model directory not found at: {self.model_path}")

        self.sample_rate = sample_rate or config.SAMPLE_RATE

        # Suppress Kaldi verbose log spam
        vosk.SetLogLevel(-1)

        # Load Kaldi model
        self.model = vosk.Model(str(self.model_path))

        # Compile grammar
        self.grammar_list = custom_grammar if custom_grammar is not None else config.get_grammar_list()
        self.grammar_json = json.dumps(self.grammar_list)
        self._valid_grammar_set = set(self.grammar_list)

        # Accumulator for segments finalized by Kaldi mid-utterance prior to VAD EOU
        self._completed_segments: List[str] = []

        # Initialize recognizer with constrained grammar FST and open-vocabulary recognizer
        self._recognizer: Optional[vosk.KaldiRecognizer] = None
        self._open_recognizer: Optional[vosk.KaldiRecognizer] = None
        self._open_streaming: bool = False
        self._has_unfinalized_frames: bool = False
        self._has_open_unfinalized_frames: bool = False
        self._init_recognizer()

    def _init_recognizer(self) -> None:
        """Create or recreate the KaldiRecognizer instance with current grammar and open recognizer."""
        self._valid_grammar_set = set(self.grammar_list)
        self._recognizer = vosk.KaldiRecognizer(
            self.model,
            self.sample_rate,
            self.grammar_json
        )
        self._recognizer.SetWords(False)
        self._recognizer.SetMaxAlternatives(3)
        self._completed_segments.clear()
        self._has_unfinalized_frames = False

        # Open-vocabulary recognizer without grammar constraints (reused across sessions)
        if self._open_recognizer is None:
            self._open_recognizer = vosk.KaldiRecognizer(
                self.model,
                self.sample_rate
            )
            self._open_recognizer.SetWords(False)
        elif self._has_open_unfinalized_frames:
            self._open_recognizer.Reset()
            self._has_open_unfinalized_frames = False
        self._open_streaming = False

    def reset(self) -> None:
        """
        Reset internal Kaldi lattice state and segment buffer for a new utterance.
        Only invokes C++ Reset() if unfinalized frames exist so Kaldi's online
        i-vector speaker adaptation state is preserved across finalized utterances.
        """
        if self._recognizer is not None and self._has_unfinalized_frames:
            self._recognizer.Reset()
            self._has_unfinalized_frames = False
        if self._open_recognizer is not None and self._has_open_unfinalized_frames:
            self._open_recognizer.Reset()
            self._has_open_unfinalized_frames = False
        self._completed_segments.clear()
        self._open_streaming = False

    @property
    def is_open_decoding(self) -> bool:
        """Whether concurrent open-vocabulary decoding is currently active."""
        return self._open_streaming

    def start_open_decoding(self) -> None:
        """Enables concurrent open-vocabulary decoding during command listening."""
        if self._open_recognizer is not None and self._has_open_unfinalized_frames:
            self._open_recognizer.Reset()
            self._has_open_unfinalized_frames = False
        self._open_streaming = True

    def stop_open_decoding(self) -> None:
        """Disables concurrent open-vocabulary decoding."""
        self._open_streaming = False

    def feed_open_chunks(self, chunks: List[Union[np.ndarray, bytes]]) -> None:
        """Feeds a batch of buffered PCM chunks into the open-vocabulary recognizer."""
        if not self._open_streaming or self._open_recognizer is None or not chunks:
            return
        for chunk in chunks:
            raw_bytes = self._to_pcm_bytes(chunk)
            self._has_open_unfinalized_frames = True
            self._open_recognizer.AcceptWaveform(raw_bytes)

    def update_grammar(self, grammar_list: List[str]) -> None:
        """Recompiles the grammar FST (used when AGENT_NAME or commands change)."""
        self.grammar_list = grammar_list
        self.grammar_json = json.dumps(self.grammar_list)
        self._init_recognizer()

    @staticmethod
    def _to_pcm_bytes(audio_chunk: Union[np.ndarray, bytes]) -> bytes:
        """Convert audio_chunk (int16/float32 ndarray or bytes) to 16-bit PCM bytes."""
        if isinstance(audio_chunk, np.ndarray):
            if audio_chunk.dtype != np.int16:
                clamped = np.clip(audio_chunk, -1.0, 1.0)
                return (clamped * 32767.0).astype(np.int16).tobytes()
            return audio_chunk.tobytes()
        return audio_chunk

    def _extract_best_text(self, res_json: dict) -> str:
        """
        Extracts the best hypothesis from Kaldi Result/FinalResult JSON.
        When N-best alternatives are present, filters out 2-gram cross-phrase
        backoff splices (such as wake-word echoes) in favor of valid grammar phrases.
        """
        if "alternatives" in res_json:
            alts = [
                a.get("text", "").strip()
                for a in res_json["alternatives"]
                if a.get("text", "").strip()
            ]
            if not alts:
                return ""
            if "[unk]" not in alts[0]:
                ww = config.wake_word
                for alt in alts:
                    words = alt.split()
                    post = " ".join(words[1:]) if (words and words[0] == ww) else alt
                    if post in self._valid_grammar_set or alt in self._valid_grammar_set:
                        return alt
            return alts[0]
        return res_json.get("text", "").strip()

    def feed_chunk(
        self,
        audio_chunk: Union[np.ndarray, bytes],
        include_partial: bool = False
    ) -> Tuple[bool, str]:
        """
        Stream an incoming audio chunk into the recognizer.
        Accepts:
            audio_chunk: int16 bytes or np.ndarray of shape (512,)
            include_partial: whether to decode and parse PartialResult JSON when not final
        Returns:
            (has_complete_segment: bool, text: str)
        """
        if self._recognizer is None:
            raise RuntimeError("VoskRecognizer is not initialized.")

        raw_bytes = self._to_pcm_bytes(audio_chunk)

        if self._open_streaming and self._open_recognizer is not None:
            self._has_open_unfinalized_frames = True
            self._open_recognizer.AcceptWaveform(raw_bytes)

        self._has_unfinalized_frames = True
        is_final = self._recognizer.AcceptWaveform(raw_bytes)
        if is_final:
            res_json = json.loads(self._recognizer.Result())
            text = self._extract_best_text(res_json)
            if text:
                self._completed_segments.append(text)
            full_prefix = " ".join(self._completed_segments).strip()
            return True, full_prefix

        if include_partial:
            partial_json = json.loads(self._recognizer.PartialResult())
            partial_text = partial_json.get("partial", "").strip()
            if self._completed_segments:
                prefix = " ".join(self._completed_segments)
                return False, f"{prefix} {partial_text}".strip()
            return False, partial_text

        return False, ""

    def get_partial_text(self) -> str:
        """Returns the current incremental partial recognition hypothesis."""
        if self._recognizer is None:
            return ""
        partial_json = json.loads(self._recognizer.PartialResult())
        partial_text = partial_json.get("partial", "").strip()
        if self._completed_segments:
            prefix = " ".join(self._completed_segments)
            return f"{prefix} {partial_text}".strip()
        return partial_text

    def get_final_result(self) -> str:
        """
        Finalizes the utterance when VAD detects End-of-Utterance (EOU).
        Flushes the Kaldi lattice, combines any earlier completed segments,
        resets state, and returns the complete normalized text.
        """
        if self._recognizer is None:
            return ""
        final_json = json.loads(self._recognizer.FinalResult())
        self._has_unfinalized_frames = False
        tail_text = self._extract_best_text(final_json)
        if tail_text:
            self._completed_segments.append(tail_text)

        full_utterance = " ".join(self._completed_segments).strip()
        self._completed_segments.clear()
        return full_utterance

    def get_open_final_result(self) -> str:
        """
        Finalizes and returns text from the open-vocabulary recognizer.
        """
        if self._open_recognizer is None:
            return ""
        if not self._has_open_unfinalized_frames and not self._open_streaming:
            return ""
        final_json = json.loads(self._open_recognizer.FinalResult())
        self._has_open_unfinalized_frames = False
        return final_json.get("text", "").strip()

    def transcribe_open_waveform(self, pcm_bytes: bytes) -> str:
        """
        One-shot open-vocabulary transcription of raw 16kHz int16 PCM bytes,
        reusing the pre-allocated open-vocabulary KaldiRecognizer.
        """
        if self._open_recognizer is None:
            self._open_recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)
            self._open_recognizer.SetWords(False)
        elif self._has_open_unfinalized_frames:
            self._open_recognizer.Reset()
            self._has_open_unfinalized_frames = False

        self._open_recognizer.AcceptWaveform(pcm_bytes)
        final_json = json.loads(self._open_recognizer.FinalResult())
        self._has_open_unfinalized_frames = False
        return final_json.get("text", "").strip()
