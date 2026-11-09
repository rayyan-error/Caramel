"""
Real-time Audio Stream Capture Engine.
Provides non-blocking, callback-driven 16kHz Mono PCM streaming via sounddevice
with thread-safe buffering, automatic PipeWire/PulseAudio input routing,
and headless simulated stream fallback.
"""

import ctypes.util
import os
import queue
import threading
from typing import Any, Optional, Union

import numpy as np

from config.settings import PROJECT_ROOT, config

# Register local PortAudio library fallback if system-wide libportaudio2 is absent
_original_find_library = ctypes.util.find_library


def _patched_find_library(name: str) -> Optional[str]:
    res = _original_find_library(name)
    if res is None and name == "portaudio":
        custom_pa = os.environ.get(
            "PORTAUDIO_PATH",
            str(PROJECT_ROOT / ".venv/lib/portaudio/libportaudio.so.2")
        )
        if os.path.isfile(custom_pa):
            return custom_pa
    return res


ctypes.util.find_library = _patched_find_library

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except (ImportError, OSError):
    sd = None
    SOUNDDEVICE_AVAILABLE = False


def resolve_default_input_device(requested_device: Optional[Union[int, str]] = None) -> Optional[Union[int, str]]:
    """
    If no device is explicitly specified, prefer 'pipewire' or 'pulse' on Linux
    so capture attaches directly to the active system audio server's microphone
    (e.g. Intel SOF DMIC array) rather than an unplugged analog ALSA jack.
    """
    if requested_device is not None:
        return requested_device
    if not SOUNDDEVICE_AVAILABLE or sd is None:
        return None
    try:
        devices = sd.query_devices()
        names = {
            str(d.get("name", "")).lower(): idx
            for idx, d in enumerate(devices)
            if d.get("max_input_channels", 0) > 0
        }
        for preferred in ("pipewire", "pulse"):
            if preferred in names:
                return preferred
    except Exception:
        pass
    return None


class AudioCapture:
    """
    Captures live audio from the default or specified input device.
    Delivers fixed-size PCM chunks via an internal thread-safe queue.
    """
    def __init__(
        self,
        sample_rate: Optional[int] = None,
        chunk_size: Optional[int] = None,
        channels: Optional[int] = None,
        dtype: Optional[str] = None,
        device: Optional[Union[int, str]] = None,
        queue_maxsize: int = 100
    ):
        self.sample_rate = sample_rate or config.SAMPLE_RATE
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        self.channels = channels or config.AUDIO_CHANNELS
        self.dtype = dtype or config.DTYPE
        self.device = resolve_default_input_device(device)

        self._buffer: queue.Queue = queue.Queue(maxsize=queue_maxsize)
        self._stream: Optional[Any] = None
        self._running: bool = False
        self._lock: threading.Lock = threading.Lock()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: Any = None
    ) -> None:
        """Callback invoked by PortAudio for each audio block."""
        chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
        try:
            self._buffer.put_nowait(chunk)
        except queue.Full:
            # Drop oldest frame to preserve real-time recency
            try:
                self._buffer.get_nowait()
                self._buffer.put_nowait(chunk)
            except queue.Empty:
                pass

    def start(self) -> None:
        """Start streaming from microphone."""
        with self._lock:
            if self._running:
                return

            if not SOUNDDEVICE_AVAILABLE or sd is None:
                raise RuntimeError("sounddevice is not available on this system.")

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=self.device,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._audio_callback
            )
            self._stream.start()
            self._running = True

    def stop(self) -> None:
        """Stop and close the audio stream."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            # Clear remaining queue
            while not self._buffer.empty():
                try:
                    self._buffer.get_nowait()
                except queue.Empty:
                    break

    @property
    def is_running(self) -> bool:
        return self._running

    def read_chunk(self, timeout: Optional[float] = 0.1) -> Optional[np.ndarray]:
        """Read a 512-sample chunk from the queue. Returns None if timed out."""
        try:
            return self._buffer.get(block=True, timeout=timeout)
        except queue.Empty:
            return None


class SimulatedAudioCapture:
    """
    Offline/Mock audio source for testing and headless validation.
    Feeds synthesized or recorded chunks sequentially without hardware.
    """
    def __init__(
        self,
        audio_data: np.ndarray,
        chunk_size: Optional[int] = None
    ):
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        self.audio_data = audio_data.reshape(-1)
        self.current_idx = 0
        self._running = False

    def start(self) -> None:
        self.current_idx = 0
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def read_chunk(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        if not self._running:
            return None
        if self.current_idx + self.chunk_size > len(self.audio_data):
            return None

        chunk = self.audio_data[self.current_idx:self.current_idx + self.chunk_size]
        self.current_idx += self.chunk_size
        return chunk
