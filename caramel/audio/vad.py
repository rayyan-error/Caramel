"""
Silero VAD ONNX Engine and 400ms End-of-Utterance (EOU) Endpointing Detector.
Handles real-time human speech classification and utterance boundary detection.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import onnxruntime as ort

from config.settings import config


class SpeechState(Enum):
    IDLE_SILENCE = "IDLE_SILENCE"
    SPEECH_ONGOING = "SPEECH_ONGOING"
    SPEECH_PAUSE = "SPEECH_PAUSE"
    EOU_TRIGGERED = "EOU_TRIGGERED"
    TIMEOUT_TRIGGERED = "TIMEOUT_TRIGGERED"
    MAX_DURATION_EXCEEDED = "MAX_DURATION_EXCEEDED"


class SileroVAD:
    """
    Stateful Silero VAD v5 ONNX runner.
    Optimized for single-thread low-latency CPU inference with pre-allocated
    64-sample rolling context window required by Silero v5's STFT frontend.
    """
    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        sample_rate: Optional[int] = None,
        chunk_size: Optional[int] = None
    ):
        self.model_path = Path(model_path or config.SILERO_VAD_MODEL_PATH)
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Silero VAD ONNX model not found at: {self.model_path}")

        sr_val = sample_rate or config.SAMPLE_RATE
        if sr_val not in (8000, 16000):
            raise ValueError(f"Silero VAD v5 supports 8000 or 16000 Hz, got {sr_val}")

        self.sample_rate = np.array(sr_val, dtype=np.int64)
        self.chunk_size = chunk_size or (512 if sr_val == 16000 else 256)
        # Silero VAD v5 requires 64 context samples at 16kHz (32 at 8kHz) prepended to each chunk
        self.context_size = 64 if sr_val == 16000 else 32

        # Configure session for minimal CPU and zero contention
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            str(self.model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"]
        )

        # Pre-allocate buffers to avoid per-chunk heap allocations
        self._input_buffer = np.zeros((1, self.context_size + self.chunk_size), dtype=np.float32)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = self._input_buffer[:, :self.context_size]
        self._ort_inputs = {
            "input": self._input_buffer,
            "state": self._state,
            "sr": self.sample_rate
        }
        self.reset()

    def reset(self) -> None:
        """Reset internal recurrent state and rolling context for a new utterance."""
        self._state.fill(0.0)
        self._input_buffer.fill(0.0)
        self._ort_inputs["state"] = self._state

    def is_speech(
        self,
        audio_chunk: np.ndarray,
        threshold: Optional[float] = None
    ) -> Tuple[bool, float]:
        """
        Infers whether a 512-sample audio chunk contains human speech.
        Accepts:
            audio_chunk: np.ndarray of shape (512,) either float32 in [-1.0, 1.0]
                         or int16 in [-32768, 32767].
        Returns:
            (is_speech: bool, speech_probability: float)
        """
        threshold = threshold if threshold is not None else config.VAD_CONFIDENCE_THRESHOLD

        if len(audio_chunk) != self.chunk_size:
            raise ValueError(f"Expected chunk size {self.chunk_size}, got {len(audio_chunk)}")

        # Convert int16 to float32 [-1.0, 1.0] directly into pre-allocated buffer after 64-sample context
        if audio_chunk.dtype == np.int16:
            np.multiply(
                audio_chunk,
                1.0 / 32768.0,
                out=self._input_buffer[0, self.context_size:],
                casting="unsafe"
            )
        else:
            self._input_buffer[0, self.context_size:] = audio_chunk

        outputs, self._state = self.session.run(None, self._ort_inputs)
        self._ort_inputs["state"] = self._state
        # Roll last 64 samples into the leading context slot for the next chunk
        self._input_buffer[0, :self.context_size] = self._input_buffer[0, -self.context_size:]

        prob = float(outputs[0][0])
        return prob >= threshold, prob


class EndOfUtteranceDetector:
    """
    State machine that processes VAD probabilities chunk-by-chunk and determines:
    1. Utterance start
    2. Hesitations / Pauses (< 400ms)
    3. End of Utterance (continuous silence >= 400ms)
    4. Speech start timeout (no speech within configured seconds)
    5. Utterance max duration safety cutoff
    """
    def __init__(
        self,
        silence_threshold_ms: Optional[int] = None,
        speech_start_timeout_s: Optional[float] = None,
        max_command_duration_s: Optional[float] = None,
        sample_rate: Optional[int] = None,
        chunk_size: Optional[int] = None
    ):
        self.silence_threshold_ms = (
            silence_threshold_ms if silence_threshold_ms is not None
            else config.SILENCE_THRESHOLD_MS
        )
        self.speech_start_timeout_s = (
            speech_start_timeout_s if speech_start_timeout_s is not None
            else config.SPEECH_START_TIMEOUT_S
        )
        self.max_command_duration_s = (
            max_command_duration_s if max_command_duration_s is not None
            else config.MAX_COMMAND_DURATION_S
        )
        self.sample_rate = sample_rate or config.SAMPLE_RATE
        self.chunk_size = chunk_size or config.CHUNK_SIZE

        # Frame duration in milliseconds (512 / 16000 * 1000 = 32.0 ms)
        self.frame_duration_ms: float = (self.chunk_size / self.sample_rate) * 1000.0

        self.reset()

    def reset(self) -> None:
        """Reset detector state for a new command session."""
        self.is_speech_active: bool = False
        self.accumulated_silence_ms: float = 0.0
        self.accumulated_speech_ms: float = 0.0
        self.total_session_elapsed_ms: float = 0.0

    def _build_meta(self, prob: float) -> Dict[str, Any]:
        return {
            "probability": prob,
            "accumulated_speech_ms": self.accumulated_speech_ms,
            "accumulated_silence_ms": self.accumulated_silence_ms,
            "total_session_ms": self.total_session_elapsed_ms,
        }

    def process_vad_result(
        self,
        is_speech: bool,
        prob: float
    ) -> Tuple[SpeechState, Dict[str, Any]]:
        """
        Update detector state based on the latest chunk's VAD determination.
        Returns:
            (SpeechState, metadata_dict)
        """
        self.total_session_elapsed_ms += self.frame_duration_ms

        # 1. Check if maximum command duration has been exceeded
        if self.is_speech_active and (self.total_session_elapsed_ms >= self.max_command_duration_s * 1000.0):
            return SpeechState.MAX_DURATION_EXCEEDED, self._build_meta(prob)

        # 2. Waiting for speech to start
        if not self.is_speech_active:
            if is_speech:
                self.is_speech_active = True
                self.accumulated_speech_ms += self.frame_duration_ms
                self.accumulated_silence_ms = 0.0
                return SpeechState.SPEECH_ONGOING, self._build_meta(prob)

            if self.total_session_elapsed_ms >= self.speech_start_timeout_s * 1000.0:
                return SpeechState.TIMEOUT_TRIGGERED, self._build_meta(prob)

            return SpeechState.IDLE_SILENCE, self._build_meta(prob)

        # 3. Speech is already active
        if is_speech:
            self.accumulated_speech_ms += self.frame_duration_ms
            self.accumulated_silence_ms = 0.0
            return SpeechState.SPEECH_ONGOING, self._build_meta(prob)
        else:
            self.accumulated_silence_ms += self.frame_duration_ms

            # Check 400ms silence threshold for End of Utterance (EOU)
            if self.accumulated_silence_ms >= self.silence_threshold_ms:
                return SpeechState.EOU_TRIGGERED, self._build_meta(prob)

            return SpeechState.SPEECH_PAUSE, self._build_meta(prob)
