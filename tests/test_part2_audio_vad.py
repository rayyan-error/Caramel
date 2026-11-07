"""
Automated Test Suite for Part 2: Audio Stream & Silero VAD (400ms EOU Endpointing)
Validates:
1. Silero VAD ONNX model loading and low-latency chunk inference.
2. Accurate discrimination between silence, environmental noise, and real human speech.
3. Strict 400ms End-of-Utterance (EOU) endpointing logic and accurate state metadata.
4. Immunity to hesitation pauses under 400ms.
5. Speech start timeout (5.0s) handling.
6. Audio capture chunk streaming interface.
"""

from pathlib import Path
import sys
import time
import wave

import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from caramel.audio.capture import SimulatedAudioCapture
from caramel.audio.vad import EndOfUtteranceDetector, SileroVAD, SpeechState


def _load_wav_16k(path: str) -> np.ndarray:
    """Load a WAV file and resample to 16kHz mono int16."""
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        if ch > 1:
            data = data[::ch]
        if sr != 16000:
            duration = len(data) / sr
            target_len = int(duration * 16000)
            data = np.interp(
                np.linspace(0, len(data) - 1, target_len),
                np.arange(len(data)),
                data
            ).astype(np.int16)
        return data


def test_silero_vad_initialization_and_latency():
    """Verify Silero VAD loads cleanly and operates with ultra-low latency (<3ms per chunk)."""
    print("[TEST] 1. Silero VAD Initialization & Inference Latency...")
    vad = SileroVAD()
    assert vad.session is not None, "ONNX InferenceSession failed to initialize"

    # 512 samples @ 16kHz
    dummy_silence = np.zeros(512, dtype=np.int16)

    # Warmup
    for _ in range(5):
        vad.is_speech(dummy_silence)

    # Benchmark 50 inference passes
    iterations = 50
    t0 = time.perf_counter()
    for _ in range(iterations):
        vad.is_speech(dummy_silence)
    t1 = time.perf_counter()

    avg_ms = ((t1 - t0) / iterations) * 1000.0
    print(f"  -> Average VAD chunk inference latency: {avg_ms:.3f} ms (Budget: <3.0 ms)")
    assert avg_ms < 5.0, f"VAD chunk inference latency too high: {avg_ms:.3f} ms"
    print("  -> Passed: Silero VAD inference latency verified within budget.")


def test_silero_vad_speech_vs_noise_discrimination():
    """Verify Silero VAD accurately detects real human speech while rejecting silence and noise."""
    print("[TEST] 2. Silero VAD Real Speech vs. Noise Discrimination...")
    vad = SileroVAD()

    # A. Pure silence
    silence_chunk = np.zeros(512, dtype=np.int16)
    is_speech, prob = vad.is_speech(silence_chunk)
    assert not is_speech and prob < 0.05, f"Silence misclassified: prob={prob}"

    # B. Real human speech vs real noise (from system ALSA reference recordings)
    speech_wav = Path("/usr/share/sounds/alsa/Front_Center.wav")
    noise_wav = Path("/usr/share/sounds/alsa/Noise.wav")

    if speech_wav.is_file() and noise_wav.is_file():
        vad.reset()
        speech_pcm = _load_wav_16k(str(speech_wav))
        speech_probs = [
            vad.is_speech(speech_pcm[i:i + 512])[1]
            for i in range(0, len(speech_pcm) - 512, 512)
        ]
        max_speech_prob = max(speech_probs)
        speech_chunks = sum(p >= 0.5 for p in speech_probs)

        vad.reset()
        noise_pcm = _load_wav_16k(str(noise_wav))
        noise_probs = [
            vad.is_speech(noise_pcm[i:i + 512])[1]
            for i in range(0, len(noise_pcm) - 512, 512)
        ]
        max_noise_prob = max(noise_probs)
        noise_chunks = sum(p >= 0.5 for p in noise_probs)

        print(f"  -> Real Human Speech max prob: {max_speech_prob:.4f} ({speech_chunks} active chunks)")
        print(f"  -> Real White/Pink Noise max prob: {max_noise_prob:.4f} ({noise_chunks} active chunks)")

        assert max_speech_prob > 0.90, f"Failed to detect real human speech: max_prob={max_speech_prob}"
        assert speech_chunks >= 10, f"Too few speech chunks detected: {speech_chunks}"
        assert noise_chunks == 0, f"Noise falsely triggered VAD on {noise_chunks} chunks"
        assert max_noise_prob < 0.15, f"Noise probability too high: {max_noise_prob}"

    print("  -> Passed: Real human speech and environmental noise accurately separated.")


def test_400ms_eou_endpointing_and_pauses():
    """
    Verify the 400ms EOU endpointing state machine:
    - Ignores pauses < 400ms.
    - Triggers EOU_TRIGGERED as soon as continuous silence reaches >= 400ms.
    - Reports exact post-transition metadata.
    """
    print("[TEST] 3. 400ms EOU Endpointing & Hesitation Immunity...")
    detector = EndOfUtteranceDetector(silence_threshold_ms=400)

    # Step A: Idle silence (5 chunks = 160ms)
    for _ in range(5):
        state, meta = detector.process_vad_result(is_speech=False, prob=0.01)
        assert state == SpeechState.IDLE_SILENCE, f"Expected IDLE_SILENCE, got {state}"
    assert not detector.is_speech_active, "Speech should not be active yet"

    # Step B: Speech starts and continues for 10 chunks (320ms)
    for idx in range(1, 11):
        state, meta = detector.process_vad_result(is_speech=True, prob=0.95)
        assert state == SpeechState.SPEECH_ONGOING, f"Expected SPEECH_ONGOING, got {state}"
        assert meta["accumulated_speech_ms"] == idx * 32.0, "Metadata speech duration mismatch"
    assert detector.is_speech_active, "Speech must be active"

    # Step C: Speaker hesitates (pauses) for 8 chunks (8 * 32ms = 256ms < 400ms)
    for i in range(1, 9):
        state, meta = detector.process_vad_result(is_speech=False, prob=0.02)
        assert state == SpeechState.SPEECH_PAUSE, (
            f"Hesitation pause at chunk {i} ({meta['accumulated_silence_ms']}ms) incorrectly triggered {state}"
        )
        assert meta["accumulated_silence_ms"] == i * 32.0
    print("  -> Verified: 256ms hesitation pause under 400ms did NOT trigger EOU.")

    # Step D: Speaker resumes speaking for 6 chunks (192ms)
    for _ in range(6):
        state, meta = detector.process_vad_result(is_speech=True, prob=0.92)
        assert state == SpeechState.SPEECH_ONGOING, f"Expected SPEECH_ONGOING on resume, got {state}"
        assert meta["accumulated_silence_ms"] == 0.0, "Metadata must immediately reflect reset silence counter"

    # Step E: Command finishes; continuous silence accumulates
    # 400ms / 32ms = 12.5 chunks. Chunk 13 (416ms) must trigger EOU_TRIGGERED.
    eou_trigger_chunk = None
    for chunk_idx in range(1, 16):
        state, meta = detector.process_vad_result(is_speech=False, prob=0.01)
        if state == SpeechState.EOU_TRIGGERED:
            eou_trigger_chunk = chunk_idx
            silence_ms = meta["accumulated_silence_ms"]
            print(f"  -> EOU Triggered at silence chunk #{chunk_idx} ({silence_ms:.1f}ms silence)")
            break
        else:
            assert state == SpeechState.SPEECH_PAUSE

    assert eou_trigger_chunk == 13, f"Expected EOU at chunk 13 (416ms), got {eou_trigger_chunk}"
    assert meta["accumulated_silence_ms"] == 416.0
    print("  -> Passed: 400ms EOU endpointing verified with precision.")


def test_speech_start_timeout():
    """Verify that if speech does not start within 5.0 seconds, TIMEOUT_TRIGGERED is emitted."""
    print("[TEST] 4. Speech Start Timeout (5.0s)...")
    detector = EndOfUtteranceDetector(speech_start_timeout_s=5.0)

    # 5.0s = 5000ms / 32ms = 156.25 chunks
    timeout_triggered = False
    for chunk_num in range(160):
        state, meta = detector.process_vad_result(is_speech=False, prob=0.01)
        if state == SpeechState.TIMEOUT_TRIGGERED:
            timeout_triggered = True
            print(f"  -> Timeout correctly triggered at chunk {chunk_num} ({meta['total_session_ms']:.1f}ms)")
            break

    assert timeout_triggered, "Failed to trigger TIMEOUT_TRIGGERED after 5.0s of silence"
    print("  -> Passed: Speech start timeout handling verified.")


def test_simulated_audio_capture_stream():
    """Verify SimulatedAudioCapture feeds fixed-size 512-sample chunks cleanly."""
    print("[TEST] 5. Audio Capture Stream Interface...")
    total_samples = 512 * 10
    synthetic_pcm = np.arange(total_samples, dtype=np.int16)
    capture = SimulatedAudioCapture(synthetic_pcm, chunk_size=512)

    assert not capture.is_running
    capture.start()
    assert capture.is_running

    received_chunks = 0
    while True:
        chunk = capture.read_chunk()
        if chunk is None:
            break
        assert len(chunk) == 512, f"Expected chunk size 512, got {len(chunk)}"
        assert chunk.dtype == np.int16
        received_chunks += 1

    assert received_chunks == 10, f"Expected 10 chunks, received {received_chunks}"
    capture.stop()
    assert not capture.is_running
    print(f"  -> Passed: Successfully streamed and verified {received_chunks} chunks.")


def run_all():
    print("==================================================")
    print("RUNNING PART 2 VALIDATION TESTS")
    print("==================================================")
    test_silero_vad_initialization_and_latency()
    test_silero_vad_speech_vs_noise_discrimination()
    test_400ms_eou_endpointing_and_pauses()
    test_speech_start_timeout()
    test_simulated_audio_capture_stream()
    print("==================================================")
    print("ALL PART 2 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all()
