"""
Automated Test Suite for Part 6: Caramel State Machine Orchestration
Validates:
1. End-to-end happy path lifecycle (DORMANT -> WAKE -> LISTENING -> EOU -> EXECUTE -> DORMANT).
2. Single-breath and two-breath wake word handling ('caramel open youtube').
3. Deterministic rejection of incomplete prefixes ('open youtube in a') without execution.
4. Deterministic rejection of unknown commands ('open youtube tomorrow') without execution.
5. Speech start timeout (5.0s silence after wake word -> return to DORMANT).
6. Emergency cancellation (cancel() -> instant return to DORMANT).
7. End-of-Utterance to execution turnaround latency (<50ms).
8. Full Real-Audio End-to-End Pipeline (Real SileroVAD + Real VoskRecognizerEngine + Real StateMachine).
"""

import ctypes
from pathlib import Path
import sys
import time

import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from caramel.audio.vad import SileroVAD
from caramel.engine.state_machine import AgentState, CaramelStateMachine
from caramel.executor.launcher import ApplicationLauncher
from caramel.recognizer.vosk_engine import VoskRecognizerEngine


class MockVAD(SileroVAD):
    """Controllable VAD for deterministic state machine testing."""
    def __init__(self, default_speech: bool = False):
        self.speech_flag = default_speech

    def reset(self):
        pass

    def is_speech(self, chunk, threshold=None):
        return self.speech_flag, 0.95 if self.speech_flag else 0.01


class MockRecognizer(VoskRecognizerEngine):
    """Controllable speech recognizer for deterministic state machine testing."""
    def __init__(self, initial_text: str = ""):
        self.text_to_return = initial_text
        self.partial_text = initial_text
        self.open_text_to_return = initial_text
        self._is_final = False
        self._open_recognizer = None
        self._open_streaming = False

    def reset(self):
        self.text_to_return = ""
        self.partial_text = ""
        self.open_text_to_return = ""
        self._open_streaming = False

    def start_open_decoding(self):
        self._open_streaming = True

    def stop_open_decoding(self):
        self._open_streaming = False

    def feed_chunk(self, chunk, include_partial=False):
        return self._is_final, self.partial_text if include_partial else ""

    def get_partial_text(self):
        return self.partial_text

    def get_final_result(self):
        res = self.text_to_return
        self.text_to_return = ""
        self.partial_text = ""
        return res

    def get_open_final_result(self):
        res = self.open_text_to_return
        self.open_text_to_return = ""
        return res

    def transcribe_open_waveform(self, pcm_bytes):
        return self.text_to_return or self.open_text_to_return


def test_happy_path_lifecycle():
    """Verify standard two-breath command execution lifecycle."""
    print("[TEST] 1. Happy Path Lifecycle (DORMANT -> WAKE -> LISTENING -> EXECUTE -> DORMANT)...")

    vad = MockVAD()
    rec = MockRecognizer()
    launcher = ApplicationLauncher(dry_run=True)
    sm = CaramelStateMachine(vad=vad, recognizer=rec, launcher=launcher)

    events = []
    sm.on_state_change = lambda old, new: events.append(f"{old.name}->{new.name}")
    sm.on_wake_detected = lambda: events.append("WAKE_DETECTED")
    sm.on_command_matched = lambda cmd, txt: events.append(f"MATCHED:{cmd.command_id}")
    sm.on_command_executed = lambda res: events.append(f"EXECUTED:{res.command_id}")

    dummy_chunk = np.zeros(512, dtype=np.int16)
    assert sm.current_state == AgentState.DORMANT

    # Step A: User speaks wake word "Caramel"
    vad.speech_flag = True
    rec.partial_text = "caramel"
    sm.process_chunk(dummy_chunk)

    assert sm.current_state == AgentState.LISTENING_COMMAND
    assert "WAKE_DETECTED" in events
    print("  -> Wake word detected; transitioned to LISTENING_COMMAND.")

    # Brief pause after wake word (10 chunks = 320ms, should NOT trigger EOU because no command spoken yet)
    vad.speech_flag = False
    for _ in range(15):
        sm.process_chunk(dummy_chunk)
    assert sm.current_state == AgentState.LISTENING_COMMAND, "Pause after wake word falsely ended listening!"

    # Step B: User speaks command "open brave"
    vad.speech_flag = True
    rec.text_to_return = "caramel open brave"
    rec.partial_text = "caramel open brave"
    for _ in range(5):
        sm.process_chunk(dummy_chunk)
    assert sm.current_state == AgentState.LISTENING_COMMAND

    # Step C: User stops speaking; 400ms silence accumulates (13 chunks @ 32ms = 416ms)
    vad.speech_flag = False
    for _ in range(13):
        sm.process_chunk(dummy_chunk)

    # Agent should have executed and returned to DORMANT
    assert sm.current_state == AgentState.DORMANT
    assert "MATCHED:CMD_OPEN_BRAVE" in events
    assert "EXECUTED:CMD_OPEN_BRAVE" in events
    assert sm.last_execution_result is not None
    assert sm.last_execution_result.success
    assert "--new-window" in sm.last_execution_result.executed_args
    assert sm.last_metrics is not None
    assert sm.last_metrics.post_speech_turnaround_ms > 0.0
    print(f"  -> State transitions: {events}")
    print("  -> Passed: Complete lifecycle executed cleanly.")


def test_single_breath_command():
    """Verify user saying 'caramel open youtube' in one breath is properly recognized."""
    print("[TEST] 2. Single-Breath Command Handling ('caramel open youtube')...")
    vad = MockVAD()
    rec = MockRecognizer()
    launcher = ApplicationLauncher(dry_run=True)
    sm = CaramelStateMachine(vad=vad, recognizer=rec, launcher=launcher)

    dummy_chunk = np.zeros(512, dtype=np.int16)

    # Wake word + command in initial continuous speech
    vad.speech_flag = True
    rec.partial_text = "caramel open youtube"
    rec.text_to_return = "caramel open youtube"
    sm.process_chunk(dummy_chunk)

    assert sm.current_state == AgentState.LISTENING_COMMAND

    # EOU silence (13 chunks = 416ms)
    vad.speech_flag = False
    for _ in range(13):
        sm.process_chunk(dummy_chunk)

    assert sm.current_state == AgentState.DORMANT
    assert sm.last_execution_result is not None
    assert sm.last_execution_result.command_id == "CMD_OPEN_YOUTUBE"
    assert sm.last_execution_result.executed_args[-1] == "https://youtube.com"
    print("  -> Passed: Single-breath wake word stripped and target command executed.")


def test_incomplete_prefix_rejection():
    """Verify incomplete prefix 'open youtube in a' is rejected without execution."""
    print("[TEST] 3. Incomplete Prefix Rejection ('open youtube in a')...")
    vad = MockVAD()
    rec = MockRecognizer()
    launcher = ApplicationLauncher(dry_run=True)
    sm = CaramelStateMachine(vad=vad, recognizer=rec, launcher=launcher)

    rejection_reasons = []
    sm.on_command_rejected = lambda reason, txt: rejection_reasons.append(reason)

    dummy_chunk = np.zeros(512, dtype=np.int16)

    # Wake word
    vad.speech_flag = True
    rec.partial_text = "caramel"
    sm.process_chunk(dummy_chunk)

    # Incomplete prefix
    rec.text_to_return = "caramel open youtube in a"
    rec.partial_text = "caramel open youtube in a"
    sm.process_chunk(dummy_chunk)

    # EOU
    vad.speech_flag = False
    for _ in range(13):
        sm.process_chunk(dummy_chunk)

    assert sm.current_state == AgentState.DORMANT
    assert sm.last_execution_result is None, "Incomplete prefix should not execute any command"
    assert any("Incomplete" in r for r in rejection_reasons)
    print(f"  -> Incomplete prefix cleanly rejected: {rejection_reasons}")
    print("  -> Passed: Incomplete prefix safely rejected without execution.")


def test_unknown_command_rejection():
    """Verify unknown command 'open youtube tomorrow' is rejected without execution."""
    print("[TEST] 4. Unknown Command Rejection ('open youtube tomorrow')...")
    vad = MockVAD()
    rec = MockRecognizer()
    launcher = ApplicationLauncher(dry_run=True)
    sm = CaramelStateMachine(vad=vad, recognizer=rec, launcher=launcher)

    rejection_reasons = []
    sm.on_command_rejected = lambda reason, txt: rejection_reasons.append(reason)

    dummy_chunk = np.zeros(512, dtype=np.int16)

    # Wake word
    vad.speech_flag = True
    rec.partial_text = "caramel"
    sm.process_chunk(dummy_chunk)

    # Unknown command
    rec.text_to_return = "caramel open youtube tomorrow"
    rec.partial_text = "caramel open youtube tomorrow"
    sm.process_chunk(dummy_chunk)

    # EOU
    vad.speech_flag = False
    for _ in range(13):
        sm.process_chunk(dummy_chunk)

    assert sm.current_state == AgentState.DORMANT
    assert sm.last_execution_result is None, "Unknown command should not execute anything"
    assert any("Unknown" in r for r in rejection_reasons)
    print(f"  -> Unknown command cleanly rejected: {rejection_reasons}")
    print("  -> Passed: Unknown command safely discarded.")


def test_speech_start_timeout():
    """Verify timeout when user says wake word but remains silent for 5.0 seconds."""
    print("[TEST] 5. Speech Start Timeout (5.0s)...")
    vad = MockVAD()
    rec = MockRecognizer()
    sm = CaramelStateMachine(vad=vad, recognizer=rec)

    timeout_reported = []
    sm.on_command_rejected = lambda reason, txt: timeout_reported.append(reason)

    dummy_chunk = np.zeros(512, dtype=np.int16)

    # Wake word
    vad.speech_flag = True
    rec.partial_text = "caramel"
    sm.process_chunk(dummy_chunk)
    assert sm.current_state == AgentState.LISTENING_COMMAND

    # Silence for 160 chunks (160 * 32ms = 5120ms > 5000ms)
    vad.speech_flag = False
    rec.partial_text = "caramel"
    rec.text_to_return = "caramel"
    for _ in range(160):
        sm.process_chunk(dummy_chunk)

    assert sm.current_state == AgentState.DORMANT
    assert any("timeout" in r.lower() for r in timeout_reported)
    print("  -> Passed: 5.0s speech timeout safely returned agent to DORMANT.")


def test_emergency_cancellation():
    """Verify cancel() immediately resets all internal state and returns to DORMANT."""
    print("[TEST] 6. Emergency Cancellation...")
    vad = MockVAD()
    rec = MockRecognizer()
    sm = CaramelStateMachine(vad=vad, recognizer=rec)

    dummy_chunk = np.zeros(512, dtype=np.int16)
    vad.speech_flag = True
    rec.partial_text = "caramel"
    sm.process_chunk(dummy_chunk)
    assert sm.current_state == AgentState.LISTENING_COMMAND

    # Emergency cancellation
    sm.cancel()
    assert sm.current_state == AgentState.DORMANT
    assert not sm.eou_detector.is_speech_active
    print("  -> Passed: Emergency cancellation verified.")


def test_turnaround_latency():
    """Verify turnaround time from EOU to execution dispatch is under 50ms."""
    print("[TEST] 7. Turnaround Latency (EOU to Execution Dispatch)...")
    vad = MockVAD()
    rec = MockRecognizer()
    launcher = ApplicationLauncher(dry_run=True)
    sm = CaramelStateMachine(vad=vad, recognizer=rec, launcher=launcher)

    dummy_chunk = np.zeros(512, dtype=np.int16)
    vad.speech_flag = True
    rec.partial_text = "caramel"
    sm.process_chunk(dummy_chunk)

    rec.text_to_return = "caramel open youtube in a new window"
    rec.partial_text = "caramel open youtube in a new window"
    sm.process_chunk(dummy_chunk)

    vad.speech_flag = False
    for _ in range(12):
        sm.process_chunk(dummy_chunk)

    # 13th chunk triggers EOU and immediate dispatch
    t0 = time.perf_counter()
    sm.process_chunk(dummy_chunk)
    turnaround_ms = (time.perf_counter() - t0) * 1000.0

    print(f"  -> EOU-to-Dispatch turnaround latency: {turnaround_ms:.3f} ms (Target: <50.0 ms)")
    assert turnaround_ms < 50.0, f"Turnaround latency too high: {turnaround_ms} ms"
    assert sm.current_state == AgentState.DORMANT
    assert sm.last_execution_result is not None
    assert sm.last_execution_result.command_id == "CMD_OPEN_YOUTUBE_NEW_WINDOW"
    print("  -> Passed: Ultra-low turnaround latency verified.")


def test_real_audio_end_to_end_pipeline():
    """
    Verify the complete unmocked CaramelStateMachine (Real SileroVAD + Real VoskRecognizerEngine)
    on synthesized 16kHz spoken audio waveforms across all 4 V1 commands (both 1-breath and 2-breath).
    """
    print("[TEST] 8. Real-Audio End-to-End Pipeline (Unmocked VAD + Vosk + StateMachine)...")
    espeak_lib_path = Path("/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1")
    if not espeak_lib_path.is_file():
        print("  -> Skipped (libespeak-ng not present)")
        return

    lib = ctypes.CDLL(str(espeak_lib_path))
    samples_list = []
    SYNTH_CB = ctypes.CFUNCTYPE(
        ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p
    )

    def _cb(wav, numsamples, events):
        if wav and numsamples > 0:
            samples_list.append(np.ctypeslib.as_array(wav, shape=(numsamples,)).copy())
        return 0

    c_cb = SYNTH_CB(_cb)
    sr = lib.espeak_Initialize(2, 0, None, 0)
    lib.espeak_SetSynthCallback(c_cb)
    lib.espeak_SetVoiceByName(b"en-us")

    def synth_16k(text_str: str) -> np.ndarray:
        samples_list.clear()
        b = text_str.encode("utf-8")
        lib.espeak_Synth(b, len(b) + 1, 0, 0, 0, 0, None, None)
        pcm = np.concatenate(samples_list)
        target_len = int(len(pcm) * 16000 / sr)
        return np.interp(
            np.linspace(0, len(pcm) - 1, target_len),
            np.arange(len(pcm)),
            pcm
        ).astype(np.int16)

    sm = CaramelStateMachine(dry_run=True)

    scenarios = [
        (
            "One-breath 'Caramel, open Brave'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open brave"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_BRAVE"
        ),
        (
            "Two-breath 'Caramel' ... [1.2s pause] ... 'open Brave'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel"),
                np.zeros(19200, dtype=np.int16),
                synth_16k("open brave"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_BRAVE"
        ),
        (
            "Prefix A 'Caramel, open YouTube'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open youtube"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_YOUTUBE"
        ),
        (
            "Prefix B 'Caramel, open YouTube in a new window'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open youtube in a new window"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_YOUTUBE_NEW_WINDOW"
        ),
        (
            "Antigravity 'Caramel, open Antigravity'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open anti gravity"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_ANTIGRAVITY"
        ),
        (
            "Terminal 'Caramel, open terminal'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open terminal"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_TERMINAL"
        ),
        (
            "Cryptomator 'Caramel, open cryptometer'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open cryptometer"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_CRYPTOMATOR"
        ),
        (
            "Gemini Tab 'Caramel, open Gemini'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open gemini"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_GEMINI"
        ),
        (
            "Gemini New Window 'Caramel, open Gemini in a new window'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open gemini in a new window"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_GEMINI_NEW_WINDOW"
        ),
        (
            "Classroom 'Caramel, open Google Classroom'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open google classroom"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_GOOGLE_CLASSROOM"
        ),
        (
            "GCR 'Caramel, open GCR'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open gcr"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_GOOGLE_CLASSROOM"
        ),
        (
            "Crunchyroll 'Caramel, open Crunchyroll'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open crunchy roll"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_CRUNCHYROLL"
        ),
        (
            "Text Editor 'Caramel, open Text Editor'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open text editor"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_TEXT_EDITOR"
        ),
        (
            "Settings 'Caramel, open Settings'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open settings"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_SETTINGS"
        ),
        (
            "Instagram 'Caramel, open Instagram'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open instagram"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_INSTAGRAM"
        ),
        (
            "GitHub 'Caramel, open GitHub'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open git hub"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_GITHUB"
        ),
        (
            "LinkedIn 'Caramel, open LinkedIn'",
            np.concatenate([
                np.zeros(3200, dtype=np.int16),
                synth_16k("caramel open linked in"),
                np.zeros(12000, dtype=np.int16)
            ]),
            "CMD_OPEN_LINKEDIN"
        ),
    ]

    for label, stream, expected_cmd_id in scenarios:
        sm.last_execution_result = None
        for i in range(0, len(stream) - 512, 512):
            sm.process_chunk(stream[i:i + 512])
        assert sm.current_state == AgentState.DORMANT
        assert sm.last_execution_result is not None, f"Failed to execute on scenario: {label}"
        assert sm.last_execution_result.command_id == expected_cmd_id, (
            f"Scenario '{label}' expected {expected_cmd_id}, got {sm.last_execution_result.command_id}"
        )
        print(f"  -> {label:54s} => {sm.last_execution_result.command_id}")

    print("  -> Passed: All real-audio spoken scenarios recognized and executed accurately.")


def run_all():
    print("==================================================")
    print("RUNNING PART 6 VALIDATION TESTS")
    print("==================================================")
    test_happy_path_lifecycle()
    test_single_breath_command()
    test_incomplete_prefix_rejection()
    test_unknown_command_rejection()
    test_speech_start_timeout()
    test_emergency_cancellation()
    test_turnaround_latency()
    test_real_audio_end_to_end_pipeline()
    print("==================================================")
    print("ALL PART 6 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all()
