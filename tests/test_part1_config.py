"""
Unit and Integration Tests for Part 1: Centralized Configuration
Tests identity switching, modular apps, acoustic grammar generation, audio settings,
model-free config loading, and command validation.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import AppConfig, CommandDefinition, Settings, config


def test_agent_identity_switch():
    """Verify AGENT_NAME is centralized and switching to Uranus propagates automatically."""
    print("[TEST] 1. Agent Identity Switch...")
    cfg = Settings(AGENT_NAME="Caramel")
    assert cfg.wake_word == "caramel", f"Expected 'caramel', got {cfg.wake_word}"
    assert "caramel" in cfg.get_grammar_list(), "Wake word 'caramel' missing from grammar list"

    # Switch identity to production name
    cfg.AGENT_NAME = "Uranus"
    assert cfg.wake_word == "uranus", f"Expected 'uranus', got {cfg.wake_word}"
    assert "uranus" in cfg.get_grammar_list(), "Wake word 'uranus' missing from grammar list"
    assert "caramel" not in cfg.get_grammar_list(), "Old wake word 'caramel' should not be in grammar list"
    print("  -> Passed: Centralized identity switch works cleanly.")


def test_audio_and_eou_parameters():
    """Verify audio capture and EOU parameters match specifications."""
    print("[TEST] 2. Audio and EOU Parameters...")
    assert config.SAMPLE_RATE == 16000, "Sample rate must be 16000 Hz"
    assert config.AUDIO_CHANNELS == 1, "Audio channels must be mono (1)"
    assert config.CHUNK_SIZE == 512, "Chunk size must be 512 samples (32ms)"
    assert config.SILENCE_THRESHOLD_MS == 400, "EOU silence threshold must be exactly 400ms"
    assert config.SPEECH_START_TIMEOUT_S == 5.0, "Speech start timeout must be 5.0s"
    print("  -> Passed: Audio parameters and 400ms EOU threshold verified.")


def test_model_independent_config_loading():
    """Confirm that configuration loading and methods do not require models to exist on disk."""
    print("[TEST] 3. Model-Independent Configuration Loading...")
    cfg = Settings(
        SILERO_VAD_MODEL_PATH=Path("/nonexistent/path/silero_vad.onnx"),
        VOSK_MODEL_PATH=Path("/nonexistent/path/vosk-model")
    )
    assert not cfg.SILERO_VAD_MODEL_PATH.exists()
    assert not cfg.VOSK_MODEL_PATH.exists()
    assert cfg.wake_word == "caramel"
    assert len(cfg.get_grammar_list()) == 35
    print("  -> Passed: Configuration loads and operates with zero dependency on installed model files.")


def test_modular_app_registry():
    """Verify modular app registry and dynamic app addition."""
    print("[TEST] 4. Modular App Registry...")
    cfg = Settings()

    # Verify built-in apps
    assert "brave" in cfg.APPS
    assert "antigravity" in cfg.APPS
    assert "vscode" in cfg.APPS
    assert "terminal" in cfg.APPS
    assert "cryptomator" in cfg.APPS
    assert "text_editor" in cfg.APPS
    assert "settings" in cfg.APPS

    brave_app = cfg.get_app("brave")
    assert brave_app is not None
    assert brave_app.new_window_args == ["--new-window"]

    # Verify Antigravity GUI executable configuration
    antigravity_app = cfg.get_app("antigravity")
    assert antigravity_app is not None
    assert "Antigravity" in antigravity_app.display_name
    assert antigravity_app.executable_path == "/home/rayyan-error/Applications/Antigravity/Antigravity-x64/antigravity"

    # Test modular duplication / new app addition
    custom_editor = AppConfig(
        identifier="sublime",
        display_name="Sublime Text",
        executable_path="/usr/bin/subl",
        new_window_args=["-n"]
    )
    cfg.register_app(custom_editor)
    assert cfg.get_app("sublime") == custom_editor
    print("  -> Passed: Modular app lookup and dynamic app registration verified.")


def test_initial_commands_validation():
    """Verify initial V1 command set and integrity against registered apps."""
    print("[TEST] 5. Initial Command Registry Integrity...")
    commands = config.COMMANDS
    assert len(commands) == 20, f"Expected 20 commands, got {len(commands)}"

    expected_phrases = {
        "open brave",
        "open antigravity",
        "open terminal",
        "open cryptometer",
        "open youtube",
        "open youtube in a new window",
        "open gemini",
        "open gemini in a new window",
        "open google classroom",
        "open google classroom in a new window",
        "open crunchyroll",
        "open crunchyroll in a new window",
        "open text editor",
        "open settings",
        "open instagram",
        "open instagram in a new window",
        "open github",
        "open github in a new window",
        "open linkedin",
        "open linkedin in a new window",
    }
    actual_phrases = {cmd.phrase for cmd in commands}
    assert actual_phrases == expected_phrases, f"Phrases mismatch: {actual_phrases} vs {expected_phrases}"

    # Ensure all commands target valid registered applications
    for cmd in commands:
        app = config.get_app(cmd.target_app)
        assert app is not None, f"Command {cmd.command_id} references unregistered app '{cmd.target_app}'"

    print("  -> Passed: All 20 commands verified with valid app targets.")


def test_vosk_grammar_generation():
    """Verify dynamic grammar list contains only clean acoustic phrases, wake word, and [unk]."""
    print("[TEST] 6. Clean Acoustic Grammar Generation...")
    grammar = config.get_grammar_list()
    expected = [
        "caramel",
        "open anti gravity",
        "open brave",
        "open classroom",
        "open classroom in a new window",
        "open crunchy roll",
        "open crunchy roll in a new window",
        "open crypto mater",
        "open crypto matter",
        "open crypto meter",
        "open crypto motor",
        "open editor",
        "open g c r",
        "open g c r in a new window",
        "open gcr",
        "open gcr in a new window",
        "open gemini",
        "open gemini in a new window",
        "open git hub",
        "open git hub in a new window",
        "open google classroom",
        "open google classroom in a new window",
        "open insta",
        "open insta in a new window",
        "open instagram",
        "open instagram in a new window",
        "open linked in",
        "open linked in in a new window",
        "open settings",
        "open settings app",
        "open terminal",
        "open text editor",
        "open youtube",
        "open youtube in a new window",
        "[unk]",
    ]
    assert grammar == expected, f"Expected {expected}, got {grammar}"
    assert "antigravity" not in grammar, "OOV compound word 'antigravity' must be acoustically decomposed"
    assert "cryptometer" not in grammar, "OOV compound word 'cryptometer' must be acoustically decomposed"
    assert "crunchyroll" not in grammar, "OOV compound word 'crunchyroll' must be acoustically decomposed"
    assert "github" not in grammar, "Compound word 'github' must be acoustically decomposed"
    assert "linkedin" not in grammar, "Compound word 'linkedin' must be acoustically decomposed"
    assert "a" not in grammar and "in" not in grammar, "Standalone function words must not pollute grammar"
    print(f"  -> Passed: Clean acoustic grammar generated ({len(grammar)} entries): {grammar}")


def run_all():
    print("==================================================")
    print("RUNNING PART 1 VALIDATION TESTS")
    print("==================================================\n")
    test_agent_identity_switch()
    test_audio_and_eou_parameters()
    test_model_independent_config_loading()
    test_modular_app_registry()
    test_initial_commands_validation()
    test_vosk_grammar_generation()
    print("\n==================================================")
    print("ALL PART 1 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_all()
