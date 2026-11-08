"""
Project Caramel / Uranus - Central Configuration Module (Part 1)
Single source of truth for all operating parameters, modular applications,
wake word identity, audio thresholds, and registered commands.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional


# Root directory of the Uranus project
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


@dataclass(frozen=True)
class AppConfig:
    """Configuration for an executable desktop application."""
    identifier: str
    display_name: str
    executable_path: str
    candidates: List[str] = field(default_factory=list)
    default_args: List[str] = field(default_factory=list)
    new_window_args: List[str] = field(default_factory=list)
    url_args: List[str] = field(default_factory=list)

    def resolve_binary(self) -> Optional[str]:
        """
        Locates the binary either via primary path, fallback candidates, or system PATH lookup.
        Returns the resolved absolute path or None if not found/not executable.
        """
        # 1. Test primary configured executable_path
        primary = os.path.expanduser(self.executable_path)
        if os.path.isabs(primary):
            if os.path.isfile(primary) and os.access(primary, os.X_OK):
                return primary
        else:
            found = shutil.which(primary)
            if found:
                return found

        # 2. Check fallback candidates
        for cand in self.candidates:
            expanded = os.path.expanduser(cand)
            if os.path.isabs(expanded):
                if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
                    return expanded
            else:
                found = shutil.which(expanded)
                if found:
                    return found
        return None


@dataclass(frozen=True)
class CommandDefinition:
    """Declarative definition for an executable voice command."""
    command_id: str
    phrase: str
    action_type: str  # e.g., 'LAUNCH_APP', 'OPEN_URL'
    target_app: str   # maps to AppConfig.identifier
    new_window: bool = False
    url: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Settings:
    """
    Central settings class.
    All runtime parameters derive from this configuration.
    """
    # -------------------------------------------------------------------------
    # 1. Identity & Wake Word
    # Change AGENT_NAME to "Uranus" for production release.
    # -------------------------------------------------------------------------
    AGENT_NAME: str = "Caramel"

    # -------------------------------------------------------------------------
    # 2. Audio Pipeline Parameters
    # -------------------------------------------------------------------------
    SAMPLE_RATE: int = 16000          # 16 kHz Mono PCM
    AUDIO_CHANNELS: int = 1           # 1 (Mono)
    CHUNK_SIZE: int = 512             # 512 samples = 32.0 ms per frame at 16kHz
    DTYPE: str = "int16"              # 16-bit PCM input

    # -------------------------------------------------------------------------
    # 3. Voice Activity Detection & Endpointing
    # -------------------------------------------------------------------------
    SILENCE_THRESHOLD_MS: int = 400   # End-of-Utterance (EOU) silence threshold (400ms)
    VAD_CONFIDENCE_THRESHOLD: float = 0.5
    SPEECH_START_TIMEOUT_S: float = 5.0 # Max wait for speech to start after wake word
    MAX_COMMAND_DURATION_S: float = 10.0 # Absolute safety cutoff for single command
    ENABLE_NOISE_SUPPRESSION: bool = False # RNNoise toggle

    # -------------------------------------------------------------------------
    # 4. Local Model Storage Paths
    # -------------------------------------------------------------------------
    SILERO_VAD_MODEL_PATH: Path = MODELS_DIR / "silero_vad.onnx"
    VOSK_MODEL_PATH: Path = MODELS_DIR / "vosk-model-small-en-us-0.15"

    # -------------------------------------------------------------------------
    # 5. Modular Application Registry
    # Easily add or duplicate applications (e.g. VS Code, Terminal, etc.)
    # -------------------------------------------------------------------------
    APPS: Dict[str, AppConfig] = field(default_factory=lambda: {
        "brave": AppConfig(
            identifier="brave",
            display_name="Brave Browser",
            executable_path=os.environ.get("BRAVE_BIN", "/usr/bin/brave-browser-stable"),
            candidates=[
                "/usr/bin/brave-browser-stable",
                "/usr/bin/brave-browser",
                "/usr/bin/brave",
                "/var/lib/flatpak/exports/bin/com.brave.Browser",
                os.path.expanduser("~/.local/share/flatpak/exports/bin/com.brave.Browser"),
                "/snap/bin/brave",
            ],
            new_window_args=["--new-window"],
        ),
        "antigravity": AppConfig(
            identifier="antigravity",
            display_name="Antigravity",
            executable_path=os.environ.get(
                "ANTIGRAVITY_BIN",
                "/snap/bin/antigravity"
            ),
            candidates=[
                "/snap/bin/antigravity",
                "antigravity",
                os.path.expanduser("~/Applications/Antigravity/Antigravity-x64/antigravity"),
                os.path.expanduser("~/Downloads/Antigravity/Antigravity-x64/antigravity"),
                "/opt/Antigravity/antigravity",
            ],
        ),
        "vscode": AppConfig(
            identifier="vscode",
            display_name="Visual Studio Code",
            executable_path=os.environ.get("VSCODE_BIN", "code"),
            candidates=[
                "code",
                "code-oss",
                "/var/lib/flatpak/exports/bin/com.visualstudio.code",
                os.path.expanduser("~/.local/share/flatpak/exports/bin/com.visualstudio.code"),
                "/snap/bin/code",
            ],
            new_window_args=["--new-window"],
        ),
        "terminal": AppConfig(
            identifier="terminal",
            display_name="GNOME Terminal",
            executable_path=os.environ.get("TERMINAL_BIN", "/usr/bin/gnome-terminal"),
            candidates=[
                "/usr/bin/gnome-terminal",
                "gnome-terminal",
                "ptyxis",
                "x-terminal-emulator",
                "konsole",
                "xfce4-terminal",
                "alacritty",
                "kitty",
            ],
            default_args=[f"--working-directory={os.path.expanduser('~')}"],
            new_window_args=["--window"],
        ),
        "cryptomator": AppConfig(
            identifier="cryptomator",
            display_name="Cryptomator",
            executable_path=os.environ.get(
                "CRYPTOMATOR_BIN",
                "/var/lib/flatpak/exports/bin/org.cryptomator.Cryptomator"
            ),
            candidates=[
                "/var/lib/flatpak/exports/bin/org.cryptomator.Cryptomator",
                os.path.expanduser("~/.local/share/flatpak/exports/bin/org.cryptomator.Cryptomator"),
                "cryptomator",
                os.path.expanduser("~/Applications/Cryptomator.AppImage"),
            ],
        ),
        "text_editor": AppConfig(
            identifier="text_editor",
            display_name="Text Editor",
            executable_path=os.environ.get("TEXT_EDITOR_BIN", "/usr/bin/gnome-text-editor"),
            candidates=[
                "/usr/bin/gnome-text-editor",
                "gnome-text-editor",
                "gedit",
                "xed",
                "kate",
                "mousepad",
                "leafpad",
            ],
            new_window_args=["--new-window"],
        ),
        "settings": AppConfig(
            identifier="settings",
            display_name="Settings",
            executable_path=os.environ.get("SETTINGS_BIN", "/usr/bin/gnome-control-center"),
            candidates=[
                "/usr/bin/gnome-control-center",
                "gnome-control-center",
                "systemsettings",
                "xfce4-settings-manager",
                "cinnamon-settings",
                "mate-control-center",
            ],
        ),
    })

    # -------------------------------------------------------------------------
    # 6. Initial Registered V1 Commands
    # -------------------------------------------------------------------------
    COMMANDS: List[CommandDefinition] = field(default_factory=lambda: [
        CommandDefinition(
            command_id="CMD_OPEN_BRAVE",
            phrase="open brave",
            action_type="LAUNCH_APP",
            target_app="brave",
            new_window=True,
        ),
        CommandDefinition(
            command_id="CMD_OPEN_ANTIGRAVITY",
            phrase="open antigravity",
            action_type="LAUNCH_APP",
            target_app="antigravity",
            new_window=False,
            aliases=["open anti gravity"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_TERMINAL",
            phrase="open terminal",
            action_type="LAUNCH_APP",
            target_app="terminal",
            new_window=True,
        ),
        CommandDefinition(
            command_id="CMD_OPEN_CRYPTOMATOR",
            phrase="open cryptometer",
            action_type="LAUNCH_APP",
            target_app="cryptomator",
            new_window=False,
            aliases=[
                "open cryptomator",
                "open crypto meter",
                "open crypto mater",
                "open crypto motor",
                "open crypto matter",
            ],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_YOUTUBE",
            phrase="open youtube",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=False,
            url="https://youtube.com",
        ),
        CommandDefinition(
            command_id="CMD_OPEN_YOUTUBE_NEW_WINDOW",
            phrase="open youtube in a new window",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=True,
            url="https://youtube.com",
        ),
        CommandDefinition(
            command_id="CMD_OPEN_GEMINI",
            phrase="open gemini",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=False,
            url="https://gemini.google.com",
        ),
        CommandDefinition(
            command_id="CMD_OPEN_GEMINI_NEW_WINDOW",
            phrase="open gemini in a new window",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=True,
            url="https://gemini.google.com",
        ),
        CommandDefinition(
            command_id="CMD_OPEN_GOOGLE_CLASSROOM",
            phrase="open google classroom",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=False,
            url="https://classroom.google.com/u/3/h/st",
            aliases=["open classroom", "open gcr", "open g c r"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_GOOGLE_CLASSROOM_NEW_WINDOW",
            phrase="open google classroom in a new window",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=True,
            url="https://classroom.google.com/u/3/h/st",
            aliases=["open classroom in a new window", "open gcr in a new window", "open g c r in a new window"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_CRUNCHYROLL",
            phrase="open crunchyroll",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=False,
            url="https://www.crunchyroll.com",
            aliases=["open crunchy roll"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_CRUNCHYROLL_NEW_WINDOW",
            phrase="open crunchyroll in a new window",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=True,
            url="https://www.crunchyroll.com",
            aliases=["open crunchy roll in a new window"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_TEXT_EDITOR",
            phrase="open text editor",
            action_type="LAUNCH_APP",
            target_app="text_editor",
            new_window=False,
            aliases=["open editor"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_SETTINGS",
            phrase="open settings",
            action_type="LAUNCH_APP",
            target_app="settings",
            new_window=False,
            aliases=["open settings app"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_INSTAGRAM",
            phrase="open instagram",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=False,
            url="https://www.instagram.com",
            aliases=["open insta"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_INSTAGRAM_NEW_WINDOW",
            phrase="open instagram in a new window",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=True,
            url="https://www.instagram.com",
            aliases=["open insta in a new window"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_GITHUB",
            phrase="open github",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=False,
            url="https://github.com",
            aliases=["open git hub"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_GITHUB_NEW_WINDOW",
            phrase="open github in a new window",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=True,
            url="https://github.com",
            aliases=["open git hub in a new window"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_LINKEDIN",
            phrase="open linkedin",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=False,
            url="https://www.linkedin.com",
            aliases=["open linked in"],
        ),
        CommandDefinition(
            command_id="CMD_OPEN_LINKEDIN_NEW_WINDOW",
            phrase="open linkedin in a new window",
            action_type="OPEN_URL",
            target_app="brave",
            new_window=True,
            url="https://www.linkedin.com",
            aliases=["open linked in in a new window"],
        ),
    ])

    # Acoustic lexicon replacements for compound words absent from small Kaldi graphs
    ACOUSTIC_SUBSTITUTIONS: Dict[str, str] = field(default_factory=lambda: {
        "antigravity": "anti gravity",
        "cryptometer": "crypto meter",
        "cryptomator": "crypto mater",
        "crunchyroll": "crunchy roll",
        "github": "git hub",
        "linkedin": "linked in",
    })

    def __post_init__(self) -> None:
        """Post-initialization to load machine-specific configuration overrides."""
        self._load_local_overrides()

    def _load_local_overrides(self) -> None:
        """Loads machine-specific application overrides from config/local_apps.json if present."""
        local_file = PROJECT_ROOT / "config" / "local_apps.json"
        if not local_file.is_file():
            return
        try:
            with open(local_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for app_id, app_data in data.items():
                app_key = app_id.lower()
                if app_key in self.APPS:
                    orig = self.APPS[app_key]
                    self.APPS[app_key] = AppConfig(
                        identifier=orig.identifier,
                        display_name=app_data.get("display_name", orig.display_name),
                        executable_path=app_data.get("executable_path", orig.executable_path),
                        candidates=app_data.get("candidates", orig.candidates),
                        default_args=app_data.get("default_args", orig.default_args),
                        new_window_args=app_data.get("new_window_args", orig.new_window_args),
                        url_args=app_data.get("url_args", orig.url_args),
                    )
        except Exception:
            pass

    @property
    def wake_word(self) -> str:
        """Returns normalized wake word from AGENT_NAME."""
        return self.AGENT_NAME.strip().lower()

    def _to_acoustic_phrase(self, phrase: str) -> str:
        """Normalizes a phrase using acoustic lexicon substitutions for Vosk FST."""
        words = phrase.strip().lower().split()
        expanded = [self.ACOUSTIC_SUBSTITUTIONS.get(w, w) for w in words]
        return " ".join(expanded)

    def get_grammar_list(self) -> List[str]:
        """
        Dynamically generates the constrained vocabulary list for Vosk ASR.
        Includes the current wake word, acoustically normalized command phrases,
        and the unknown token '[unk]'.
        """
        grammar_phrases = {self._to_acoustic_phrase(self.wake_word)}
        for cmd in self.COMMANDS:
            phrases_to_add = [cmd.phrase] + cmd.aliases
            for p in phrases_to_add:
                p_acoustic = self._to_acoustic_phrase(p)
                if p_acoustic:
                    grammar_phrases.add(p_acoustic)

        grammar_list = sorted(grammar_phrases)
        grammar_list.append("[unk]")
        return grammar_list

    def get_app(self, identifier: str) -> Optional[AppConfig]:
        """Retrieve application configuration by identifier."""
        return self.APPS.get(identifier.lower())

    def register_app(self, app_config: AppConfig) -> None:
        """Add or update an application configuration."""
        self.APPS[app_config.identifier.lower()] = app_config


# Global default configuration instance
config = Settings()
