# Changelog & Release Notes — Project Caramel / Uranus

All notable changes, architectural milestones, bug fixes, and performance optimizations across every version of **Project Caramel** (production codename: **Uranus**) are documented in this file.

- **Author:** Mohammad Rayyan ([`@rayyan-error`](https://github.com/rayyan-error)) — Student at Christ University, Central Campus, Bangalore (Reg. No: `2641528`)
- **Repository:** [https://github.com/rayyan-error/Caramel](https://github.com/rayyan-error/Caramel)

---

## [v0.2.5] — 2026-11-09
### Instant Service CLI, Acoustic-Trie Bijection, Lazy Open-Vocabulary Decoding & System-Wide Optimization

Version `0.2.5` finalizes the `v0.2.x` architecture with a global `caramel` CLI controller, a full codebase audit eliminating all acoustic/Trie and search-query collisions across all 53 voice commands, and an ~4x ASR speedup on standard commands via lazy open-vocabulary decoding.

### Added
- **Global `caramel` CLI Service Controller (`scripts/caramel`, `install.sh`)**:
  - Added the `caramel` CLI executable linked to `~/.local/bin/caramel` for instant service management from any terminal:
    - `caramel restart` — Restarts the background `caramel.service` daemon immediately.
    - `caramel status` — Displays active service status, PID, memory RSS, and recent logs.
    - `caramel logs` — Streams live `journalctl` logs from the background service.
    - `caramel start` / `caramel stop` — Starts or stops the systemd user service.
    - `caramel run` / `caramel --dry-run` — Runs the agent interactively in the foreground terminal.
  - Added automated test coverage in `tests/test_part7_cli_and_service.py` for the CLI controller and `restart` workflow.
- **Acoustic-to-Trie Bijection & Real-Audio Collision Verification (`tests/test_v02_features.py`)**:
  - Added automated bijection assertions verifying that every acoustic phrase expansion in `VoskRecognizer` maps deterministically back to its originating `CommandDefinition` in `CommandTrie`.
  - Added search query edge-case unit tests covering queries with embedded engine names (`"google"`, `"youtube"`) and leading prepositions (`"in"`, `"on"`, `"for"`).

### Fixed
- **Acoustic Grammar & Trie Synchronization (10 Out-of-Vocabulary Commands Fixed)**:
  - Updated `CommandRegistry.register()` (`caramel/engine/registry.py`) to automatically index both raw phrases/aliases and their `config._to_acoustic_phrase()` expanded forms into `CommandTrie`. Previously, commands containing acronyms or out-of-vocabulary words (`espro`, `kp`, `chatgpt`, `vlc`, `gimp`, `krita`, `cryptomator`, `gcr`, `linkedin`, `crunchyroll`) were emitted by Vosk in expanded acoustic form and rejected by the Trie.
- **Phonetic & Coalescence Collisions Across All 53 Commands (`config/settings.py`, `caramel/recognizer/vosk_engine.py`)**:
  - Added `"gmail": "g mail"` to `ACOUSTIC_SUBSTITUTIONS` so `"gmail"` is never dropped as `[unk]` by the Kaldi grammar FST.
  - Added phonetic/coalescence aliases for `CMD_OPEN_LINKEDIN_NEW_WINDOW` (`"open linked in a new window"`), `CMD_OPEN_SPOTIFY` / `CMD_OPEN_SPOTIFY_NEW_WINDOW` (`"open spot file"`), `CMD_OPEN_GMAIL` / `CMD_OPEN_GMAIL_NEW_WINDOW` (`"open g mail"`), `CMD_OPEN_OBS` (`"open o b s"`), `CMD_OPEN_CHATGPT`, `CMD_OPEN_VLC`, `CMD_OPEN_KRITA`, and `CMD_UNMUTE_VOLUME`.
  - Enabled `SetMaxAlternatives(3)` with `_extract_best_text()` in `VoskRecognizer` (`caramel/recognizer/vosk_engine.py`) to filter out Kaldi 2-gram cross-phrase backoff splices in favor of valid complete commands.
- **Dynamic Search Engine Query Collisions (`caramel/engine/search.py`)**:
  - Fixed engine extraction precedence so trailing engine specifiers (e.g., `"search youtube api documentation on google"`) are evaluated before leading engine specifiers, preventing query topics starting with `"youtube"` or `"google"` from being stripped.
  - Required explicit prepositions (`on`, `in`, `from`, `via`) or trailing `for` on leading engine matches and removed bare `"on"` / `"in"` stripping so queries like `"search in memory database"`, `"search on premises deployment"`, `"search for loop in python"`, and `"search how to log in"` remain intact.
- **Runtime, Audio, Launcher & Installer Bug Fixes**:
  - `caramel/executor/launcher.py`: Added missing `import shutil` and fallback `PATH` resolution for `SYSTEM_ACTION` binaries (`wpctl`) when executing volume commands.
  - `caramel/engine/state_machine.py`: Synced custom `--name` CLI wake-word overrides into `VoskRecognizer`'s grammar FST at startup.
  - `caramel/audio/capture.py`: Extracted mono channel 0 (`indata[:, 0].copy()`) when capturing from multi-channel audio devices to prevent chunk size exceptions in Silero VAD.
  - `caramel/utils/lock.py`: Fixed file descriptor leak in `SingleInstanceLock.acquire()` when `fcntl.flock()` fails on an already-locked file, and handled relative lockfile paths without `makedirs("")` errors.
  - `caramel/utils/profiler.py`: Hardened `/proc/self/stat` parsing using `rfind(")")` so process names containing spaces or parentheses cannot shift column indices.
  - `run.py`: Replaced buffered `sys.stdin.read(1)` in `TerminalEscListener.check_esc_pressed()` with unbuffered `os.read(self._fd, 32)` so standalone `ESC` presses are distinguished from multi-byte arrow/function key sequences.
  - `install.sh`: Defined `PROJECT_ROOT="${SCRIPT_DIR}"` so `~/.local/bin/caramel` is never symlinked to a broken `/scripts/caramel` path.
  - `scripts/service_manager.sh` & `scripts/caramel`: Fixed `journalctl --user-u` typo to `journalctl --user -u`, guarded `systemctl --user status` with `|| true` under `set -e`, and added fallback to `python3` when `.venv` is absent.
  - `scripts/configure_apps.py` & `scripts/download_models.py`: Improved `.desktop` `Exec=` parser to skip `env`, `VAR=val`, and `%U`/`%F` tokens, and made model downloads atomic via `.tmp` staging.
  - `caramel/__init__.py`: Synchronized `__version__ = "0.2.5"`.

### Performance Optimizations
- **Lazy On-Demand Open-Vocabulary Decoding (~4x Faster Standard Commands)**:
  - `StateMachine` (`caramel/engine/state_machine.py`) and `VoskRecognizer` (`caramel/recognizer/vosk_engine.py`) now keep the unconstrained open-vocabulary Kaldi decoder idle during normal utterances and only activate/replay buffered utterance chunks when `"search"` is detected in the constrained grammar recognizer.
- **Zero-Allocation Hot-Path Improvements**:
  - `VoskRecognizer`: Tracked `_has_unfinalized_frames` / `_has_open_unfinalized_frames` to skip redundant `KaldiRecognizer.Reset()` calls after `FinalResult()` (preserving Kaldi online i-vector speaker adaptation), and reused `self._open_recognizer` in `transcribe_open_waveform()` instead of reallocating a C++ recognizer (~80 ms saved per call).
  - `SileroVADDetector` (`caramel/audio/vad.py`): Eliminated redundant `_context` numpy copies and reused pre-allocated `_ort_inputs` dict across every 32 ms audio frame.
  - `CommandTrie` (`caramel/engine/trie.py`): Added `__slots__` to `TrieNode`.
  - `search.py`: Pre-compiled all regex patterns at module import time.
  - `profiler.py`: Cached `SC_PAGE_SIZE` and `SC_CLK_TCK` constants once at import time.

---

## [v0.2.0] — 2026-11-09
### Dynamic Web Search, Christ University Portals, Expanded Desktop Suite & PipeWire Volume Controls

Version `0.2.0` introduced hybrid constrained + open-vocabulary speech recognition for dynamic Google and YouTube searches, dedicated voice shortcuts for Christ University portals, a 19-application Linux desktop suite, and native PipeWire/WirePlumber volume controls.

### Added
- **Hybrid Constrained + Open-Vocabulary Vosk Recognizer (`caramel/recognizer/vosk_engine.py`, `caramel/engine/state_machine.py`)**:
  - Dual Kaldi recognizer pipeline pairing strict grammar recognition for deterministic command triggering with open-vocabulary transcription for free-form search queries.
  - Added `ACOUSTIC_SUBSTITUTIONS` in `config/settings.py` to map out-of-vocabulary names and acronyms (`youtube`, `chatgpt`, `espro`, `gimp`, `krita`, `vlc`, `gcr`, `linkedin`, `crunchyroll`, `cryptomator`) to phonetic equivalents in `vosk-model-small-en-us-0.15`.
- **Dynamic Web Search Engine (`caramel/engine/search.py`, `caramel/engine/registry.py`)**:
  - Voice search parser extracting query text, target search engine (`Google` or `YouTube`), and window mode (`new tab` vs. `"in a new window"`).
  - Automatic URL encoding (`https://www.google.com/search?q=...` and `https://www.youtube.com/results?search_query=...`).
- **Christ University Student Portals (`config/settings.py`)**:
  - Registered voice commands and aliases for the **CUE Student Portal** (`https://cue.christuniversity.in/main/home` via `"open christ university portal"`, `"open portal"`, `"open cue"`, `"open espro"`, `"open attendance"`) and **KnowledgePro** (`https://kp.christuniversity.in/KnowledgePro/Login.do` via `"open kp"`, `"open knowledge pro"`).
- **Expanded Linux Desktop Application & Web Suite (`config/settings.py`)**:
  - Added desktop launchers for LibreOffice (`Start Center`, `Writer`, `Calc`, `Impress`, `Draw`), GNOME utilities (`Files`, `Calculator`, `System Monitor`, `Text Editor`, `Settings`), creative & media apps (`VLC`, `GIMP`, `Krita`, `OBS Studio`, `ChatGPT Desktop`, `Cryptomator`), and web destinations (`Gmail`, `Spotify`, `Instagram`, `Crunchyroll`, `Reddit`, `Wikipedia`).
  - Updated Google Antigravity binary path resolution to support Snap installations (`/snap/bin/antigravity`).
- **PipeWire / WirePlumber System Audio Volume Controls (`caramel/executor/launcher.py`, `config/settings.py`)**:
  - Added `SYSTEM_ACTION` execution mode in `CommandLauncher` to run `wpctl` audio commands (`"volume up"`, `"volume down"`, `"mute volume"`, `"unmute volume"`).
- **Test Suite Expansion (`tests/test_v02_features.py`)**:
  - Added 400+ lines of unit and integration tests covering v0.2 dynamic search, portals, desktop apps, and volume controls.

---

## [v0.1.0] — 2026-11-08
### Initial Release — Deterministic Offline Voice-Controlled Linux Desktop Agent

Version `0.1.0` established the core offline voice-control architecture for Linux (Zorin OS / Ubuntu) with zero cloud dependencies, sub-millisecond frame latencies, and universal multi-PC installer support.

### Added
- **Real-Time Audio Capture & Silero VAD v5 Pipeline (`caramel/audio/capture.py`, `caramel/audio/vad.py`)**:
  - Non-blocking 16 kHz mono 16-bit PCM microphone stream via `sounddevice` / PortAudio with thread-safe ring buffering.
  - Local Silero VAD v5 ONNX inference (~0.10 ms per 32 ms chunk) and 400 ms End-of-Utterance (EOU) silence detector.
- **Constrained-Grammar Streaming Vosk ASR (`caramel/recognizer/vosk_engine.py`)**:
  - Offline Kaldi speech recognition (`vosk-model-small-en-us-0.15`) restricted to registered command vocabulary plus `[unk]` rejection (~0.47 ms per 32 ms chunk).
- **Deterministic Prefix Tree & 3-State Execution Engine (`caramel/engine/trie.py`, `caramel/engine/registry.py`, `caramel/engine/state_machine.py`)**:
  - `CommandTrie` providing $O(k)$ longest-prefix matching (~0.50 µs) to cleanly disambiguate base commands from `"in a new window"` suffixed variants.
  - 3-state machine (`DORMANT` -> `LISTENING` -> `EXECUTING`) supporting both single-breath (`"Caramel, open YouTube"`) and two-step (`"Caramel"` ... `"open YouTube"`) commands.
- **Safe Detached Process Launcher & Runtime Utilities (`caramel/executor/launcher.py`, `caramel/utils/lock.py`, `caramel/utils/profiler.py`)**:
  - `CommandLauncher` spawning detached processes via `subprocess.Popen(..., start_new_session=True)` with `DEVNULL` I/O and no `shell=True`.
  - POSIX `fcntl.flock` single-instance lock (`/tmp/caramel_agent.lock`) and monotonic latency/RSS profiler.
- **Universal Linux Installer & Multi-PC Auto-Configuration (`install.sh`, `scripts/configure_apps.py`, `scripts/download_models.py`, `scripts/service_manager.sh`, `systemd/caramel.service`)**:
  - One-click `install.sh` installer verifying apt packages, building `.venv`, downloading ONNX/Vosk models, auto-discovering native/Snap/Flatpak binaries into `config/local_apps.json`, and configuring the user `systemd` service.
  - Initial command set covering Brave Browser, Google Antigravity, GNOME Terminal, YouTube, Gemini, Claude, WhatsApp, Google Classroom, GitHub, and LinkedIn.
  - Complete 7-part verification test suite (`tests/test_part1_config.py` through `tests/test_part7_cli_and_service.py`).
