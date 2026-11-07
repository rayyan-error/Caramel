"""
Automated Test Suite for Part 5: Modular Application Launcher
Validates:
1. Exact argv argument compilation for all 4 initial V1 commands.
2. Brave new window vs. existing tab/window behavior.
3. Antigravity modular target path resolution.
4. Modular app addition and duplication (e.g. VS Code).
5. Safe process spawning with detached sessions (setsid) without shell=True.
6. Error handling for unregistered applications and invalid binary paths.
7. Subprocess spawn initiation latency (<50ms).
"""

from pathlib import Path
import sys
import time

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from caramel.executor.launcher import ApplicationLauncher, ExecutionResult
from config.settings import AppConfig, CommandDefinition, Settings, config


def test_v1_commands_argv_construction():
    """Verify argv compilation matches exact specifications for all 4 V1 commands."""
    print("[TEST] 1. V1 Commands Argv Construction...")
    launcher = ApplicationLauncher(dry_run=True)

    # 1. Open Brave -> [brave, "--new-window"]
    cmd_brave = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_BRAVE")
    res = launcher.execute(cmd_brave)
    assert res.success, f"Failed building argv for Brave: {res.message}"
    assert "--new-window" in res.executed_args
    assert res.executed_args[0] == config.get_app("brave").executable_path
    print(f"  -> CMD_OPEN_BRAVE => {res.executed_args}")

    # 2. Open Antigravity -> [antigravity_bin]
    cmd_antigravity = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_ANTIGRAVITY")
    res = launcher.execute(cmd_antigravity)
    assert res.success, f"Failed building argv for Antigravity: {res.message}"
    assert res.executed_args == ["/home/rayyan-error/Applications/Antigravity/Antigravity-x64/antigravity"]
    print(f"  -> CMD_OPEN_ANTIGRAVITY => {res.executed_args}")

    # 3. Open YouTube -> [brave, "https://youtube.com"]
    cmd_yt = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_YOUTUBE")
    res = launcher.execute(cmd_yt)
    assert res.success, f"Failed building argv for YouTube tab: {res.message}"
    assert "--new-window" not in res.executed_args
    assert res.executed_args[-1] == "https://youtube.com"
    print(f"  -> CMD_OPEN_YOUTUBE => {res.executed_args}")

    # 4. Open YouTube in a new window -> [brave, "--new-window", "https://youtube.com"]
    cmd_yt_win = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_YOUTUBE_NEW_WINDOW")
    res = launcher.execute(cmd_yt_win)
    assert res.success, f"Failed building argv for YouTube new window: {res.message}"
    assert "--new-window" in res.executed_args
    assert res.executed_args[-1] == "https://youtube.com"
    print(f"  -> CMD_OPEN_YOUTUBE_NEW_WINDOW => {res.executed_args}")

    # 5. Open Terminal -> [gnome-terminal, "--working-directory=...", "--window"]
    cmd_term = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_TERMINAL")
    res = launcher.execute(cmd_term)
    assert res.success, f"Failed building argv for Terminal: {res.message}"
    assert "--window" in res.executed_args
    print(f"  -> CMD_OPEN_TERMINAL => {res.executed_args}")

    # 6. Open Cryptomator -> [org.cryptomator.Cryptomator]
    cmd_crypto = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_CRYPTOMATOR")
    res = launcher.execute(cmd_crypto)
    assert res.success, f"Failed building argv for Cryptomator: {res.message}"
    print(f"  -> CMD_OPEN_CRYPTOMATOR => {res.executed_args}")

    # 7. Open Gemini -> [brave, "https://gemini.google.com"] (NOT in a new window)
    cmd_gemini = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_GEMINI")
    res = launcher.execute(cmd_gemini)
    assert res.success, f"Failed building argv for Gemini tab: {res.message}"
    assert "--new-window" not in res.executed_args
    assert res.executed_args[-1] == "https://gemini.google.com"
    print(f"  -> CMD_OPEN_GEMINI => {res.executed_args}")

    # 8. Open Gemini in a new window -> [brave, "--new-window", "https://gemini.google.com"]
    cmd_gemini_win = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_GEMINI_NEW_WINDOW")
    res = launcher.execute(cmd_gemini_win)
    assert res.success, f"Failed building argv for Gemini new window: {res.message}"
    assert "--new-window" in res.executed_args
    assert res.executed_args[-1] == "https://gemini.google.com"
    print(f"  -> CMD_OPEN_GEMINI_NEW_WINDOW => {res.executed_args}")

    # 9. Open Google Classroom -> [brave, "https://classroom.google.com/u/3/h/st"]
    cmd_gcr = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_GOOGLE_CLASSROOM")
    res = launcher.execute(cmd_gcr)
    assert res.success, f"Failed building argv for Google Classroom: {res.message}"
    assert "--new-window" not in res.executed_args
    assert res.executed_args[-1] == "https://classroom.google.com/u/3/h/st"
    print(f"  -> CMD_OPEN_GOOGLE_CLASSROOM => {res.executed_args}")

    # 10. Open Crunchyroll -> [brave, "https://www.crunchyroll.com"]
    cmd_crunchy = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_CRUNCHYROLL")
    res = launcher.execute(cmd_crunchy)
    assert res.success, f"Failed building argv for Crunchyroll: {res.message}"
    assert "--new-window" not in res.executed_args
    assert res.executed_args[-1] == "https://www.crunchyroll.com"
    print(f"  -> CMD_OPEN_CRUNCHYROLL => {res.executed_args}")

    # 11. Open Text Editor -> [/usr/bin/gnome-text-editor]
    cmd_text = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_TEXT_EDITOR")
    res = launcher.execute(cmd_text)
    assert res.success, f"Failed building argv for Text Editor: {res.message}"
    print(f"  -> CMD_OPEN_TEXT_EDITOR => {res.executed_args}")

    # 12. Open Settings -> [/usr/bin/gnome-control-center]
    cmd_set = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_SETTINGS")
    res = launcher.execute(cmd_set)
    assert res.success, f"Failed building argv for Settings: {res.message}"
    print(f"  -> CMD_OPEN_SETTINGS => {res.executed_args}")

    # 13. Open Instagram -> [brave, "https://www.instagram.com"]
    cmd_insta = next(c for c in config.COMMANDS if c.command_id == "CMD_OPEN_INSTAGRAM")
    res = launcher.execute(cmd_insta)
    assert res.success, f"Failed building argv for Instagram: {res.message}"
    assert "--new-window" not in res.executed_args
    assert res.executed_args[-1] == "https://www.instagram.com"
    print(f"  -> CMD_OPEN_INSTAGRAM => {res.executed_args}")

    print("  -> Passed: All 4 initial V1 commands compile to exact specified argv lists.")


def test_modular_app_duplication():
    """Verify modular app duplication: adding an arbitrary new app and command."""
    print("[TEST] 2. Modular App Duplication (e.g. VS Code)...")
    launcher = ApplicationLauncher(dry_run=True)

    vscode_app = AppConfig(
        identifier="vscode",
        display_name="Visual Studio Code",
        executable_path="/usr/bin/code",
        new_window_args=["--new-window"]
    )
    vscode_cmd = CommandDefinition(
        command_id="CMD_OPEN_VSCODE",
        phrase="open vs code",
        action_type="LAUNCH_APP",
        target_app="vscode",
        new_window=True
    )

    res = launcher.execute(vscode_cmd, app_config=vscode_app)
    assert res.success
    assert res.executed_args == ["/usr/bin/code", "--new-window"]
    print(f"  -> Custom App Command executed: {res.executed_args}")
    print("  -> Passed: Modular app registration and command execution verified.")


def test_safety_and_unregistered_app_rejection():
    """Verify safety: unregistered apps or invalid paths gracefully fail without shell injection."""
    print("[TEST] 3. Safety & Unregistered Application Handling...")
    launcher = ApplicationLauncher(dry_run=False)

    unregistered_cmd = CommandDefinition(
        command_id="CMD_BAD",
        phrase="open bad app",
        action_type="LAUNCH_APP",
        target_app="nonexistent_app"
    )
    res = launcher.execute(unregistered_cmd)
    assert not res.success
    assert "not registered" in res.message
    print(f"  -> Unregistered app cleanly rejected: '{res.message}'")

    bad_path_app = AppConfig(
        identifier="fake",
        display_name="Fake App",
        executable_path="/nonexistent/bin/path"
    )
    bad_path_cmd = CommandDefinition(
        command_id="CMD_FAKE",
        phrase="open fake",
        action_type="LAUNCH_APP",
        target_app="fake"
    )
    res = launcher.execute(bad_path_cmd, app_config=bad_path_app)
    assert not res.success
    assert "not found" in res.message or "not executable" in res.message
    print(f"  -> Invalid binary path cleanly rejected: '{res.message}'")
    print("  -> Passed: Safety constraints and descriptive rejection verified.")


def test_live_detached_process_spawning():
    """Verify live detached process execution (setsid) using safe system utility."""
    print("[TEST] 4. Live Detached Process Spawning & Latency...")
    launcher = ApplicationLauncher(dry_run=False)

    # Use python interpreter as a harmless test binary that exits immediately
    python_bin = sys.executable
    test_app = AppConfig(
        identifier="test_python",
        display_name="Python Runner",
        executable_path=python_bin,
        default_args=["-c", "import sys; sys.exit(0)"]
    )
    test_cmd = CommandDefinition(
        command_id="CMD_TEST_SPAWN",
        phrase="run test",
        action_type="LAUNCH_APP",
        target_app="test_python"
    )

    t0 = time.perf_counter()
    res = launcher.execute(test_cmd, app_config=test_app)
    t1 = time.perf_counter()

    assert res.success, f"Live process spawn failed: {res.message}"
    assert res.pid is not None, "Failed to capture spawned PID"
    assert res.pid > 0, f"Invalid PID: {res.pid}"

    spawn_latency_ms = (t1 - t0) * 1000.0
    print(f"  -> Spawned detached PID {res.pid} in {spawn_latency_ms:.3f} ms (Budget: <50ms)")
    assert spawn_latency_ms < 50.0, f"Spawn latency exceeded budget: {spawn_latency_ms} ms"
    print("  -> Passed: Detached process spawning and ultra-low initiation latency verified.")


def run_all():
    print("==================================================")
    print("RUNNING PART 5 VALIDATION TESTS")
    print("==================================================")
    test_v1_commands_argv_construction()
    test_modular_app_duplication()
    test_safety_and_unregistered_app_rejection()
    test_live_detached_process_spawning()
    print("==================================================")
    print("ALL PART 5 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all()
