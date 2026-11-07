# Project Caramel / Uranus (v0.1.0)
## Lightweight, Voice-Controlled Linux Desktop Agent

**Caramel** (production name: **Uranus**) is an ultra-fast, predictable, locally operated voice-controlled desktop agent designed specifically for Linux (Zorin OS / Ubuntu).

---

## 1. Core Engineering Philosophy

- **Zero Cloud / Zero LLMs**: Completely offline. No cloud APIs, generative AI, semantic inference, or autonomous guessing.
- **Deterministic Action**: Every executable command is explicitly registered in a prefix tree (Trie). Unknown or ambiguous speech is discarded.
- **Ultra-Low Latency**:
  - Silero VAD chunk inference: **~0.10 ms** per 32 ms frame.
  - Vosk streaming ASR chunk inference: **~0.47 ms** per 32 ms frame.
  - Trie command lookup: **~0.50 µs** (0.0005 ms).
  - Subprocess spawn latency: **~0.40 ms**.
  - Turnaround time post-speech: dominated almost entirely by the configured 400 ms End-of-Utterance (EOU) validation window.
- **Minimal Footprint**: Operates within ~15–85 MB RAM and < 2% single-core CPU while dormant.

---

## 2. Quick Start & Universal Linux Installation

Clone the repository and run the installer:

```bash
git clone https://github.com/rayyan-error/Caramel.git
cd Caramel
./install.sh
```

The installer automatically:
1. Verifies system dependencies (`python3-venv`, `libportaudio2`, `libespeak-ng1`, `curl`, `unzip`).
2. Creates the `.venv` Python virtual environment and installs packages from `requirements.txt`.
3. Downloads the offline AI models (`silero_vad.onnx` and `vosk-model-small-en-us-0.15`).
4. **Auto-discovers applications** on your specific Linux system (Brave, Chrome, GNOME Terminal, Konsole, Alacritty, GNOME Text Editor, Gedit, Settings, Cryptomator) and writes your local configuration.
5. Runs the self-diagnostic verification test suite.
6. Offers to configure the background user systemd service for startup on login.

---

## 3. Directory Structure

```text
Caramel/
├── config/
│   ├── __init__.py
│   ├── settings.py          # Central identity, audio parameters, candidate applications & Trie registry
│   └── local_apps.json      # Machine-specific autodetected application overrides (gitignored)
├── caramel/
│   ├── audio/
│   │   ├── capture.py       # Non-blocking 16kHz PCM streaming (PipeWire/Pulse/ALSA)
│   │   └── vad.py           # Silero VAD v5 ONNX engine & 400ms EOU detector
│   ├── recognizer/
│   │   └── vosk_engine.py   # Streaming Vosk recognizer with dynamic constrained grammar
│   ├── engine/
│   │   ├── trie.py          # Deterministic prefix tree resolving prefix collisions
│   │   ├── registry.py      # Command registration & alias management
│   │   └── state_machine.py # 3-state engine: DORMANT -> LISTENING -> EXECUTING
│   ├── executor/
│   │   └── launcher.py      # Detached process spawner (setsid, no shell=True)
│   └── utils/
│       ├── lock.py          # POSIX single-instance file lock
│       └── profiler.py      # Monotonic latency & resource monitor
├── models/
│   ├── silero_vad.onnx      # Local Silero VAD v5 model (2.3 MB)
│   └── vosk-model-small-en-us-0.15/ # Local Kaldi acoustic model
├── systemd/
│   └── caramel.service      # User systemd service unit template
├── scripts/
│   ├── configure_apps.py    # Desktop app autodetection & path resolver
│   ├── download_models.py   # Automated offline AI model downloader
│   └── service_manager.sh   # Background service manager (install/start/stop/status)
├── install.sh               # One-click universal installer
├── tests/                   # Complete automated test suites
└── run.py                   # Main CLI runtime entry point
└── requirements.txt         # Pinned dependencies
```

---

## 3. Initial V1 Commands

| Spoken Phrase | Action | Behavior |
| :--- | :--- | :--- |
| `"Caramel, open Brave"` | `CMD_OPEN_BRAVE` | Spawns a dedicated new window of Brave browser (`--new-window`). |
| `"Caramel, open Antigravity"` | `CMD_OPEN_ANTIGRAVITY` | Spawns Antigravity from `/home/rayyan-error/Applications/Antigravity/Antigravity-x64/antigravity`. |
| `"Caramel, open YouTube"` | `CMD_OPEN_YOUTUBE` | Opens `https://youtube.com` in Brave (attaches to existing tab/window or launches Brave). |
| `"Caramel, open YouTube in a new window"` | `CMD_OPEN_YOUTUBE_NEW_WINDOW` | Opens `https://youtube.com` in a separate Brave window (`--new-window`). |

> **Prefix Disambiguation**: Saying `"Caramel, open YouTube in a new window"` will **never** trigger `"open YouTube"` prematurely. The engine buffers speech incrementally and dispatches only after VAD verifies the complete utterance has ended (400 ms silence).

---

## 4. Usage

### A. Run in Terminal (Foreground)
Activate virtualenv and start:
```bash
source .venv/bin/activate
python run.py
```

### B. Dry-Run Mode (Validation without spawning windows)
```bash
python run.py --dry-run
```

### C. Switch Identity to Production Name ("Uranus")
```bash
python run.py --name Uranus
```
*(Or permanently edit `AGENT_NAME = "Uranus"` in `config/settings.py`)*

### D. List Audio Input Devices
```bash
python run.py --list-devices
```

### E. Run Full Test Suite & Latency Benchmark
```bash
python run.py --benchmark
# Or run all unit tests:
for t in tests/test_part*.py; do python "$t"; done
```

---

## 5. Background Operation (Systemd User Service)

To run Caramel automatically in the background on Zorin OS:

```bash
# Install and enable on user login
./scripts/service_manager.sh install

# Start service
./scripts/service_manager.sh start

# Check service status
./scripts/service_manager.sh status

# View live logs
./scripts/service_manager.sh logs

# Stop service
./scripts/service_manager.sh stop
```

---

## 6. Extending with New Modular Applications

To register a new desktop application (e.g., VS Code, Terminal), add it to `APPS` in `config/settings.py`:

```python
"vscode": AppConfig(
    identifier="vscode",
    display_name="Visual Studio Code",
    executable_path="/usr/bin/code",
    new_window_args=["--new-window"],
)
```

Then register the command in `COMMANDS`:
```python
CommandDefinition(
    command_id="CMD_OPEN_VSCODE",
    phrase="open vs code",
    action_type="LAUNCH_APP",
    target_app="vscode",
    new_window=True,
)
```
The Trie, grammar compilation, and launcher adapt automatically.
