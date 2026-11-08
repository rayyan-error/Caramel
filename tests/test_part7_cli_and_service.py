"""
Automated Test Suite for Part 7: CLI Runner, Latency Profiler & Systemd Service
Validates:
1. POSIX Single-instance file lock acquisition and release.
2. Low-overhead resource monitoring (Memory RSS & CPU times).
3. CLI argument parsing, device listing, and benchmark modes.
4. Systemd user service unit configuration and paths.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from caramel.utils.lock import SingleInstanceLock
from caramel.utils.profiler import PerformanceMonitor, CommandMetrics


def test_single_instance_lock():
    """Verify single-instance locking prevents duplicate process execution."""
    print("[TEST] 1. Single-Instance File Lock...")
    with tempfile.NamedTemporaryFile() as tmp:
        lock1 = SingleInstanceLock(lockfile_path=tmp.name)
        lock2 = SingleInstanceLock(lockfile_path=tmp.name)

        # First instance acquires lock
        assert lock1.acquire(), "Failed to acquire lock on first attempt"

        # Second instance must fail while lock1 is held
        assert not lock2.acquire(), "Second instance incorrectly acquired already held lock"

        # Release first lock
        lock1.release()

        # Second instance can now acquire lock
        assert lock2.acquire(), "Failed to acquire lock after first instance released it"
        lock2.release()

    print("  -> Passed: Single-instance lock cleanly prevents duplicates.")


def test_performance_monitoring():
    """Verify memory and CPU monitoring returns valid non-negative readings."""
    print("[TEST] 2. Performance & Resource Monitoring...")
    rss_mb = PerformanceMonitor.get_memory_rss_mb()
    print(f"  -> Current process RSS: {rss_mb:.2f} MB")
    assert rss_mb > 0.0, "Memory RSS must be greater than 0"
    assert rss_mb < 300.0, f"Memory RSS unexpectedly high: {rss_mb} MB"

    utime, stime = PerformanceMonitor.get_cpu_times()
    print(f"  -> CPU times: user={utime:.3f}s, sys={stime:.3f}s")
    assert utime >= 0.0 and stime >= 0.0

    # Test CommandMetrics calculation
    m = CommandMetrics(
        wake_detected_time=1.0,
        speech_start_time=1.5,
        eou_detected_time=2.0,
        match_completed_time=2.0005,
        execution_completed_time=2.0010
    )
    assert m.speech_duration_ms == 500.0
    assert abs(m.trie_lookup_ms - 0.5) < 0.01
    assert abs(m.post_speech_turnaround_ms - 1.0) < 0.01
    print("  -> Passed: Resource monitoring and timing metrics verified.")


def test_systemd_unit_configuration():
    """Verify systemd service file contains required directives and correct paths."""
    print("[TEST] 3. Systemd Unit Configuration...")
    unit_path = PROJECT_ROOT / "systemd/caramel.service"
    assert unit_path.is_file(), f"Service file not found at {unit_path}"

    content = unit_path.read_text()
    assert "ExecStart=" in content
    assert "run.py" in content
    assert "Restart=on-failure" in content
    assert "WantedBy=default.target graphical-session.target" in content
    assert "KillMode=process" in content
    print(f"  -> Systemd service file verified ({len(content.splitlines())} lines).")
    print("  -> Passed: Systemd service unit valid.")


def test_cli_modes_and_benchmarks():
    """Verify CLI flags: --help, --list-devices, and --benchmark."""
    print("[TEST] 4. CLI Execution Modes...")
    python_bin = sys.executable
    run_py = str(PROJECT_ROOT / "run.py")

    # A. --help
    res = subprocess.run([python_bin, run_py, "--help"], capture_output=True, text=True)
    assert res.returncode == 0, f"--help failed: {res.stderr}"
    assert "Project Caramel" in res.stdout

    # B. --list-devices
    res = subprocess.run([python_bin, run_py, "--list-devices"], capture_output=True, text=True)
    assert res.returncode == 0, f"--list-devices failed: {res.stderr}"
    assert "Available Input Audio Devices" in res.stdout

    # C. --benchmark
    res = subprocess.run([python_bin, run_py, "--benchmark"], capture_output=True, text=True)
    assert res.returncode == 0, f"--benchmark failed: {res.stderr}"
    assert "ALL PART 6 TESTS PASSED" in res.stdout
    print("  -> Passed: CLI --help, --list-devices, and --benchmark modes verified.")


def test_caramel_cli_script():
    """Verify scripts/caramel CLI controller (--version, --help, status)."""
    print("[TEST] 5. Caramel CLI Script Controller...")
    caramel_script = str(PROJECT_ROOT / "scripts" / "caramel")
    assert os.path.isfile(caramel_script), "scripts/caramel missing"
    assert os.access(caramel_script, os.X_OK), "scripts/caramel is not executable"

    # 1. Version check
    res = subprocess.run([caramel_script, "--version"], capture_output=True, text=True)
    assert res.returncode == 0, f"caramel --version failed: {res.stderr}"
    assert "Caramel v0.2.5" in res.stdout

    # 2. Help check
    res = subprocess.run([caramel_script, "--help"], capture_output=True, text=True)
    assert res.returncode == 0, f"caramel --help failed: {res.stderr}"
    assert "caramel restart" in res.stdout
    assert "caramel status" in res.stdout

    # 3. Status check
    res = subprocess.run([caramel_script, "status"], capture_output=True, text=True)
    assert res.returncode == 0, f"caramel status failed: {res.stderr}"
    assert "caramel.service" in res.stdout
    print("  -> Passed: scripts/caramel CLI controller verified.")


def run_all():
    print("==================================================")
    print("RUNNING PART 7 VALIDATION TESTS")
    print("==================================================")
    test_single_instance_lock()
    test_performance_monitoring()
    test_systemd_unit_configuration()
    test_cli_modes_and_benchmarks()
    test_caramel_cli_script()
    print("==================================================")
    print("ALL PART 7 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all()
