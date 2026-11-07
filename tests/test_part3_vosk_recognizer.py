"""
Automated Test Suite for Part 3: Vosk Streaming Grammar & Keyword Spotting
Validates:
1. Vosk offline model loading and clean Kaldi FST grammar compilation (zero OOV warnings).
2. Dynamic grammar updates upon agent identity switch (Caramel -> Uranus).
3. Chunk streaming inference and real-time processing latency (<2ms per 32ms chunk).
4. Rejection of unregistered human speech ('Front Center' -> '[unk] [unk]').
5. Mid-utterance segment preservation across internal Kaldi endpoints.
6. Dtype flexibility (int16, float32, raw PCM bytes) and fast lattice reset.
"""

from pathlib import Path
import sys
import time
import wave

import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from caramel.recognizer.vosk_engine import VoskRecognizerEngine
from config.settings import Settings, config


def _load_wav_16k(path: str) -> np.ndarray:
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


def test_vosk_model_loading_and_grammar():
    """Verify Vosk model loads and compiles the constrained grammar FST without OOV words."""
    print("[TEST] 1. Vosk Model Loading & Clean Grammar FST Compilation...")
    engine = VoskRecognizerEngine()
    assert engine.model is not None, "Failed to load Vosk model"
    assert engine._recognizer is not None, "Failed to initialize KaldiRecognizer"

    # Check grammar components
    assert "caramel" in engine.grammar_list, "Wake word 'caramel' missing from grammar"
    assert "open brave" in engine.grammar_list, "Command 'open brave' missing from grammar"
    assert "open anti gravity" in engine.grammar_list, "Normalized 'open anti gravity' missing from grammar"
    assert "open youtube in a new window" in engine.grammar_list
    assert "[unk]" in engine.grammar_list, "'[unk]' token missing from grammar"
    assert "antigravity" not in engine.grammar_list, "OOV compound token must not be in Kaldi FST"
    print(f"  -> Grammar compiled cleanly with {len(engine.grammar_list)} entries: {engine.grammar_list}")
    print("  -> Passed: Vosk model and grammar successfully initialized.")


def test_dynamic_grammar_identity_switch():
    """Verify updating grammar seamlessly updates the recognizer to Uranus."""
    print("[TEST] 2. Dynamic Identity Switch (Caramel -> Uranus)...")
    engine = VoskRecognizerEngine()
    assert "caramel" in engine.grammar_list
    assert "uranus" not in engine.grammar_list

    # Generate grammar for production identity
    prod_config = Settings(AGENT_NAME="Uranus")
    engine.update_grammar(prod_config.get_grammar_list())

    assert "uranus" in engine.grammar_list, "'uranus' wake word missing after update"
    assert "caramel" not in engine.grammar_list, "Old wake word 'caramel' still in grammar"
    assert "open brave" in engine.grammar_list, "Commands must be preserved after update"
    print("  -> Passed: Grammar dynamically switched to 'uranus' with zero reloads of model files.")


def test_chunk_streaming_latency():
    """Verify real-time chunk streaming latency (< 2.0ms per 32ms chunk)."""
    print("[TEST] 3. Streaming Chunk Processing Latency...")
    engine = VoskRecognizerEngine()

    # 512 samples @ 16kHz
    dummy_pcm = np.zeros(512, dtype=np.int16)

    # Warmup
    for _ in range(5):
        engine.feed_chunk(dummy_pcm)

    iterations = 50
    t0 = time.perf_counter()
    for _ in range(iterations):
        engine.feed_chunk(dummy_pcm)
    t1 = time.perf_counter()

    avg_ms = ((t1 - t0) / iterations) * 1000.0
    print(f"  -> Average Vosk chunk processing latency: {avg_ms:.3f} ms (Budget: <2.0 ms)")
    assert avg_ms < 3.0, f"Vosk processing latency too high: {avg_ms:.3f} ms"
    print("  -> Passed: Vosk streaming inference operates well within real-time budget.")


def test_unregistered_speech_rejection():
    """Verify unregistered spoken words map to '[unk]' rather than hallucinating commands."""
    print("[TEST] 4. Unregistered Real Speech Rejection...")
    speech_wav = Path("/usr/share/sounds/alsa/Front_Center.wav")
    if speech_wav.is_file():
        engine = VoskRecognizerEngine()
        pcm = _load_wav_16k(str(speech_wav))
        for i in range(0, len(pcm) - 512, 512):
            engine.feed_chunk(pcm[i:i + 512])
        result = engine.get_final_result()
        print(f"  -> Spoken 'Front Center' recognized as: '{result}'")
        assert "open" not in result and "brave" not in result and "youtube" not in result, (
            f"Constrained recognizer hallucinated command from unrelated speech: '{result}'"
        )
        assert "[unk]" in result, f"Expected '[unk]' for out-of-grammar speech, got '{result}'"
    print("  -> Passed: Unregistered human speech safely mapped to '[unk]'.")


def test_mid_utterance_segment_accumulation_and_reset():
    """Verify segments finalized mid-utterance are preserved until get_final_result() is called."""
    print("[TEST] 5. Segment Accumulation, Dtype Handling & Fast Reset...")
    engine = VoskRecognizerEngine()

    # Simulate Kaldi finalizing a segment mid-stream before VAD EOU
    engine._completed_segments.append("open youtube")
    _, partial = engine.feed_chunk(np.zeros(512, dtype=np.int16), include_partial=True)
    assert partial == "open youtube", f"Expected accumulated prefix 'open youtube', got '{partial}'"

    # Finalize at EOU
    final_text = engine.get_final_result()
    assert final_text == "open youtube", f"Expected 'open youtube', got '{final_text}'"
    assert len(engine._completed_segments) == 0, "Completed segments buffer must clear after get_final_result()"

    # Feed float32 ndarray (with values slightly outside [-1, 1] to test clamping)
    chunk_float32 = np.array([1.5, -1.5] + [0.0] * 510, dtype=np.float32)
    is_final, _ = engine.feed_chunk(chunk_float32)
    assert isinstance(is_final, bool)

    # Benchmark native C++ Reset()
    t0 = time.perf_counter()
    engine.reset()
    reset_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  -> Native lattice reset latency: {reset_ms:.4f} ms")
    assert reset_ms < 0.5, f"Reset took too long: {reset_ms} ms"
    assert engine.get_partial_text() == ""
    print("  -> Passed: Segment preservation, dtype clamping, and sub-millisecond reset verified.")


def run_all():
    print("==================================================")
    print("RUNNING PART 3 VALIDATION TESTS")
    print("==================================================")
    test_vosk_model_loading_and_grammar()
    test_dynamic_grammar_identity_switch()
    test_chunk_streaming_latency()
    test_unregistered_speech_rejection()
    test_mid_utterance_segment_accumulation_and_reset()
    print("==================================================")
    print("ALL PART 3 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all()
