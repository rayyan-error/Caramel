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

        # Accumulator for segments finalized by Kaldi mid-utterance prior to VAD EOU
        self._completed_segments: List[str] = []

        # Initialize recognizer with constrained grammar FST and open-vocabulary recognizer
        self._recognizer: Optional[vosk.KaldiRecognizer] = None
        self._open_recognizer: Optional[vosk.KaldiRecognizer] = None
        self._open_streaming: bool = False
        self._init_recognizer()

    def _init_recognizer(self) -> None:
        """Create or recreate the KaldiRecognizer instance with current grammar and open recognizer."""
        self._recognizer = vosk.KaldiRecognizer(
            self.model,
            self.sample_rate,
            self.grammar_json
        )
        self._recognizer.SetWords(False)
        self._completed_segments.clear()

        # Open-vocabulary recognizer without grammar constraints
        self._open_recognizer = vosk.KaldiRecognizer(
            self.model,
            self.sample_rate
        )
        self._open_recognizer.SetWords(False)
        self._open_streaming = False

    def reset(self) -> None:
        """Reset internal Kaldi lattice state and segment buffer for a new utterance."""
        if self._recognizer is not None:
            self._recognizer.Reset()
        if self._open_recognizer is not None:
            self._open_recognizer.Reset()
        self._completed_segments.clear()
        self._open_streaming = False

    def start_open_decoding(self) -> None:
        """Enables concurrent open-vocabulary decoding during command listening."""
        if self._open_recognizer is not None:
            self._open_recognizer.Reset()
        self._open_streaming = True

    def stop_open_decoding(self) -> None:
        """Disables concurrent open-vocabulary decoding."""
        self._open_streaming = False

    def update_grammar(self, grammar_list: List[str]) -> None:
        """Recompiles the grammar FST (used when AGENT_NAME or commands change)."""
        self.grammar_list = grammar_list
        self.grammar_json = json.dumps(self.grammar_list)
        self._init_recognizer()

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

        if isinstance(audio_chunk, np.ndarray):
            if audio_chunk.dtype != np.int16:
                # Safely clamp float32 [-1.0, 1.0] and convert to int16 PCM bytes
                clamped = np.clip(audio_chunk, -1.0, 1.0)
                int16_chunk = (clamped * 32767.0).astype(np.int16)
                raw_bytes = int16_chunk.tobytes()
            else:
                raw_bytes = audio_chunk.tobytes()
        else:
            raw_bytes = audio_chunk

        if self._open_streaming and self._open_recognizer is not None:
            self._open_recognizer.AcceptWaveform(raw_bytes)

        is_final = self._recognizer.AcceptWaveform(raw_bytes)
        if is_final:
            res_json = json.loads(self._recognizer.Result())
            text = res_json.get("text", "").strip()
            if text:
                self._completed_segments.append(text)
            return True, text

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
        tail_text = final_json.get("text", "").strip()
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
        final_json = json.loads(self._open_recognizer.FinalResult())
        return final_json.get("text", "").strip()

    def transcribe_open_waveform(self, pcm_bytes: bytes) -> str:
        """
        One-shot open-vocabulary transcription of raw 16kHz int16 PCM bytes.
        """
        rec = vosk.KaldiRecognizer(self.model, self.sample_rate)
        rec.AcceptWaveform(pcm_bytes)
        final_json = json.loads(rec.FinalResult())
        return final_json.get("text", "").strip()
