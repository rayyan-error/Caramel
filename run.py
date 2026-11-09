#!/usr/bin/env python3
"""
Project Caramel / Uranus - Voice-Controlled Linux Desktop Automation Utility.
Main Entry Point and Runtime Daemon.
"""

import argparse
import os
from pathlib import Path
import select
import signal
import sys
from typing import Optional, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from caramel.audio.capture import AudioCapture, SOUNDDEVICE_AVAILABLE
from caramel.engine.state_machine import AgentState, CaramelStateMachine
from caramel.utils.lock import SingleInstanceLock
from caramel.utils.profiler import PerformanceMonitor
from config.settings import config


def list_audio_devices() -> None:
    """Print all available input devices."""
    if not SOUNDDEVICE_AVAILABLE:
        print("[Error] sounddevice / PortAudio is not available.")
        return
    import sounddevice as sd
    devices = sd.query_devices()
    print("\n--- Available Input Audio Devices ---")
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            print(f"[{idx}] {dev['name']} (Inputs: {dev['max_input_channels']}, Default SR: {int(dev['default_samplerate'])} Hz)")
    print("-------------------------------------\n")


def _parse_device_arg(val: Optional[str]) -> Optional[Union[int, str]]:
    if val is None:
        return None
    val_str = val.strip()
    if val_str.isdigit():
        return int(val_str)
    return val_str


class TerminalEscListener:
    """
    Non-blocking terminal keyboard listener for interactive sessions.
    Pressing ESC cancels any active command interaction and returns to DORMANT.
    Safe no-op when running as a headless background systemd daemon.
    """
    def __init__(self):
        self._active = False
        self._fd: Optional[int] = None
        self._old_settings = None

    def start(self) -> None:
        if not sys.stdin.isatty():
            return
        try:
            import termios
            import tty
            self._fd = sys.stdin.fileno()
            self._old_settings = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
            self._active = True
        except Exception:
            self._active = False

    def check_esc_pressed(self) -> bool:
        if not self._active or self._fd is None:
            return False
        try:
            rlist, _, _ = select.select([self._fd], [], [], 0.0)
            if rlist:
                data = os.read(self._fd, 32)
                if data == b"\x1b":  # Standalone ESC key (not multi-byte arrow escape sequence)
                    return True
        except Exception:
            pass
        return False

    def stop(self) -> None:
        if self._active and self._fd is not None and self._old_settings is not None:
            try:
                import termios
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass
        self._active = False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Project Caramel / Uranus - Voice-Controlled Linux Desktop Agent"
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Override agent name / wake word (e.g. --name Uranus)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and log commands without actually launching GUI applications"
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Specify audio input device index or name (e.g. --device pipewire or --device 11)"
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List all audio capture devices and exit"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run fast offline performance benchmark and exit"
    )

    args = parser.parse_args()

    if args.list_devices:
        list_audio_devices()
        sys.exit(0)

    # 1. Identity configuration
    if args.name:
        config.AGENT_NAME = args.name.strip()

    agent_name = config.AGENT_NAME
    wake_word = config.wake_word
    parsed_device = _parse_device_arg(args.device)

    if args.benchmark:
        print(f"\n[Caramel Benchmark] Starting offline profiling for agent '{agent_name}'...")
        rss_mb = PerformanceMonitor.get_memory_rss_mb()
        print(f"[Benchmark] Initial Memory RSS: {rss_mb:.2f} MB")
        from tests import test_part6_state_machine
        test_part6_state_machine.run_all()
        final_rss_mb = PerformanceMonitor.get_memory_rss_mb()
        print(f"[Benchmark] Final Memory RSS: {final_rss_mb:.2f} MB\n")
        sys.exit(0)

    # 2. Prevent duplicate running instances
    lock = SingleInstanceLock()
    if not lock.acquire():
        print(f"[Error] Another instance of {agent_name} is already running. Exiting.")
        sys.exit(1)

    # 3. Initialize components
    try:
        audio = AudioCapture(device=parsed_device)
        agent = CaramelStateMachine(dry_run=args.dry_run)
    except Exception as exc:
        print(f"[Initialization Error] {exc}")
        lock.release()
        sys.exit(1)

    print("=" * 64)
    print(f"  {agent_name.upper()} - Voice-Controlled Linux Desktop Agent (v{config.VERSION})")
    print("=" * 64)
    print(f"  Identity:               '{agent_name}' (Wake Word: '{wake_word}')")
    print(f"  Audio Input Device:     {audio.device!r} ({config.SAMPLE_RATE} Hz Mono PCM)")
    print(f"  EOU Silence Threshold:  {config.SILENCE_THRESHOLD_MS} ms")
    print(f"  Speech Start Timeout:   {config.SPEECH_START_TIMEOUT_S} s")
    print(f"  Dry Run Mode:           {args.dry_run}")
    print(f"  Process Memory RSS:     {PerformanceMonitor.get_memory_rss_mb():.1f} MB")
    print("=" * 64)

    # 4. Wire observer callbacks for terminal output
    def on_state_change(old_state: AgentState, new_state: AgentState) -> None:
        if new_state == AgentState.DORMANT:
            print(f"[{agent_name}] Status: DORMANT (Waiting for '{wake_word}')...")

    def on_wake() -> None:
        print(f"\n⚡ [{agent_name}] Wake word '{wake_word}' detected! Speak command (or press ESC to cancel)...")

    def on_matched(cmd, text: str) -> None:
        print(f"🎯 [{agent_name}] Matched: '{text}' -> {cmd.command_id}")

    def on_executed(res) -> None:
        turnaround = (
            f"{agent.last_metrics.post_speech_turnaround_ms:.2f}ms"
            if agent.last_metrics else f"{res.execution_latency_ms:.2f}ms"
        )
        print(f"🚀 [{agent_name}] Executed: {res.message} (Post-EOU turnaround: {turnaround})\n")

    def on_rejected(reason: str, text: str) -> None:
        print(f"⚠️ [{agent_name}] Discarded: '{text}' (Reason: {reason})\n")

    agent.on_state_change = on_state_change
    agent.on_wake_detected = on_wake
    agent.on_command_matched = on_matched
    agent.on_command_executed = on_executed
    agent.on_command_rejected = on_rejected

    # 5. Signal handling for graceful shutdown
    stop_flag = False

    def handle_shutdown(signum, frame) -> None:
        nonlocal stop_flag
        print(f"\n[{agent_name}] Shutdown signal received. Exiting cleanly...")
        stop_flag = True

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    esc_listener = TerminalEscListener()

    # 6. Start audio capture stream
    try:
        audio.start()
        esc_listener.start()
        print(f"[{agent_name}] Online and listening on microphone. Press ESC to cancel active command, Ctrl+C to stop.\n")
        print(f"[{agent_name}] Status: DORMANT (Waiting for '{wake_word}')...")
    except Exception as exc:
        esc_listener.stop()
        print(f"[Audio Error] Could not start microphone stream: {exc}")
        lock.release()
        sys.exit(1)

    # 7. Processing loop
    try:
        while not stop_flag:
            if esc_listener.check_esc_pressed():
                if agent.current_state != AgentState.DORMANT:
                    print(f"\n🛑 [{agent_name}] Emergency ESC pressed! Cancelled active command interaction.")
                    agent.cancel()
            chunk = audio.read_chunk(timeout=0.1)
            if chunk is not None:
                agent.process_chunk(chunk)
    finally:
        esc_listener.stop()
        audio.stop()
        agent.cancel()
        lock.release()
        print(f"[{agent_name}] Stopped. Goodbye.")


if __name__ == "__main__":
    main()
