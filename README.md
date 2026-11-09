# Project Caramel / Uranus (v0.2.5)
## Lightweight, Voice-Controlled Linux Desktop Agent

**Caramel** (production name: **Uranus**) is an ultra-fast, predictable, locally operated voice-controlled desktop agent designed specifically for Linux (Zorin OS / Ubuntu).

---

## 1. Core Engineering Philosophy

- **Zero Cloud / Zero LLMs**: Completely offline. No cloud APIs, generative AI, semantic inference, or autonomous guessing.
- **Deterministic Action**: Every executable command is explicitly registered in a prefix tree (Trie). Unknown or ambiguous speech is discarded.
- **Dynamic Search Engine (v0.2+)**: Open-vocabulary Kaldi intent extraction automatically formats dynamic queries for Google and YouTube.
- **Instant Service CLI (v0.2.5)**: Type `caramel restart`, `caramel status`, or `caramel logs` from any terminal.
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
4. **Auto-discovers applications** on your specific Linux system (Brave, Antigravity, LibreOffice, Files, Calculator, System Monitor, VLC, GIMP, Krita, OBS, ChatGPT, Terminal, Cryptomator) and writes your local configuration.
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
│   │   └── vosk_engine.py   # Hybrid streaming Vosk recognizer (constrained grammar + open vocabulary)
│   ├── engine/
│   │   ├── search.py        # Dynamic query parser & URL generator (Google / YouTube)
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
│   ├── caramel              # Global CLI controller (start/stop/restart/status/logs/run)
│   ├── configure_apps.py    # Desktop app autodetection & path resolver
│   ├── download_models.py   # Automated offline AI model downloader
│   └── service_manager.sh   # Background service manager (install/start/stop/status)
├── install.sh               # One-click universal installer
├── CHANGELOG.md             # Full version history & release notes (v0.1.0 -> v0.2.5)
├── tests/                   # Complete automated test suites (Part 1 to Part 7 + v02)
├── run.py                   # Main CLI runtime entry point
└── requirements.txt         # Pinned dependencies
```

---

## 4. Voice Commands Reference

### A. Dynamic Web Searches (Google & YouTube)
| Spoken Phrase | Engine | Target Action |
| :--- | :--- | :--- |
| `"Caramel, search <query>"` | Google | Opens Google search in a new tab in Brave |
| `"Caramel, search <query> on google"` | Google | Opens Google search in a new tab in Brave |
| `"Caramel, search <query> in a new window"` | Google | Launches separate Brave window with Google search |
| `"Caramel, search <query> on youtube"` | YouTube | Opens YouTube search results in a new tab in Brave |
| `"Caramel, search <query> on youtube in a new window"` | YouTube | Launches separate Brave window with YouTube search |

### B. Student & University Portals (Christ University)
| Spoken Phrase / Aliases | Destination |
| :--- | :--- |
| `"Caramel, open christ university portal"` / `"open portal"` / `"open cue"` / `"open espro"` / `"open attendance"` | [CUE Student Portal](https://cue.christuniversity.in/main/home) |
| `"Caramel, open kp"` / `"open k p"` / `"open knowledge pro"` | [KnowledgePro Portal](https://kp.christuniversity.in/KnowledgePro/Login.do) |
| *(Append `"in a new window"` to open in a dedicated browser window)* | |

### C. Desktop Applications & Office Suite
| Spoken Phrase / Aliases | Target Application |
| :--- | :--- |
| `"Caramel, open Antigravity"` | Google Antigravity (`/snap/bin/antigravity`) |
| `"Caramel, open Brave"` | Brave Browser (`--new-window`) |
| `"Caramel, open Terminal"` | GNOME Terminal (`--window`) |
| `"Caramel, open LibreOffice"` | LibreOffice Start Center (`libreoffice`) |
| `"Caramel, open writer"` / `"open document"` | LibreOffice Writer (`libreoffice --writer`) |
| `"Caramel, open calc"` / `"open spreadsheet"` | LibreOffice Calc (`libreoffice --calc`) |
| `"Caramel, open impress"` / `"open presentation"` | LibreOffice Impress (`libreoffice --impress`) |
| `"Caramel, open draw"` | LibreOffice Draw (`libreoffice --draw`) |
| `"Caramel, open files"` / `"open file manager"` | GNOME Files / Nautilus |
| `"Caramel, open calculator"` | GNOME Calculator |
| `"Caramel, open system monitor"` / `"open task manager"` | GNOME System Monitor |
| `"Caramel, open ChatGPT app"` | ChatGPT Desktop App |
| `"Caramel, open VLC"` / `"open media player"` | VLC Media Player (Flatpak/native) |
| `"Caramel, open GIMP"` / `"open image editor"` | GIMP (native/Flatpak) |
| `"Caramel, open Krita"` / `"open paint"` | Krita Digital Painting (Flatpak) |
| `"Caramel, open OBS"` / `"open stream studio"` | OBS Studio (Flatpak) |
| `"Caramel, open Cryptomator"` | Cryptomator Flatpak |
| `"Caramel, open text editor"` | GNOME Text Editor |
| `"Caramel, open settings"` | GNOME Control Center |

### D. Web Destinations
| Spoken Phrase | Target URL |
| :--- | :--- |
| `"Caramel, open YouTube"` | `https://youtube.com` |
| `"Caramel, open Gemini"` | `https://gemini.google.com` |
| `"Caramel, open Claude"` | `https://claude.ai` |
| `"Caramel, open WhatsApp"` | `https://web.whatsapp.com` |
| `"Caramel, open Spotify"` | `https://open.spotify.com` |
| `"Caramel, open Gmail"` / `"open mail"` | `https://mail.google.com` |
| `"Caramel, open Google Classroom"` / `"open gcr"` | `https://classroom.google.com` |
| `"Caramel, open GitHub"` | `https://github.com` |
| `"Caramel, open LinkedIn"` | `https://www.linkedin.com` |
| `"Caramel, open Instagram"` | `https://www.instagram.com` |
| `"Caramel, open Crunchyroll"` | `https://www.crunchyroll.com` |
| `"Caramel, open Reddit"` | `https://reddit.com` |
| `"Caramel, open Wikipedia"` / `"open wiki"` | `https://en.wikipedia.org` |

### E. System Audio Volume Controls (PipeWire / WirePlumber)
| Spoken Phrase | Action |
| :--- | :--- |
| `"Caramel, volume up"` / `"increase volume"` | Increases default audio sink volume by 5% (`wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+`) |
| `"Caramel, volume down"` / `"decrease volume"` | Decreases default audio sink volume by 5% (`wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-`) |
| `"Caramel, mute volume"` / `"mute audio"` | Mutes default audio sink (`wpctl set-mute @DEFAULT_AUDIO_SINK@ 1`) |
| `"Caramel, unmute volume"` / `"unmute audio"` | Unmutes default audio sink (`wpctl set-mute @DEFAULT_AUDIO_SINK@ 0`) |

---

## 5. Instant Service Management CLI (`caramel`)

Caramel provides a native command-line utility linked to `~/.local/bin/caramel` (in your default `$PATH`):

| Command | Action |
| :--- | :--- |
| `caramel restart` | **Instantly restarts** the background Caramel systemd service |
| `caramel status` | Shows current service status, memory RSS, and recent journal logs |
| `caramel logs` | Follows real-time live logs from the background daemon (`journalctl -f`) |
| `caramel start` | Starts the background user service |
| `caramel stop` | Stops the background service |
| `caramel run` | Runs the agent directly in the foreground terminal |
| `caramel --dry-run` | Runs the agent in foreground dry-run verification mode |
| `caramel --help` | Shows full CLI usage and options |

---

## 6. Manual Foreground Usage

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
*(Or edit `AGENT_NAME = "Uranus"` in `config/settings.py`)*

### D. Run Full Test Suite
```bash
for t in tests/test_*.py; do python "$t"; done
```

## 7. Extending with New Modular Applications

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

---

## 8. Version History & Release Notes

See [`CHANGELOG.md`](./CHANGELOG.md) for the complete release record across all versions:

- **`v0.2.5` (2026-11-09)** — Global `caramel` CLI service controller (`caramel restart`, `status`, `logs`), full acoustic-to-Trie bijection fixing 10 out-of-vocabulary commands, phonetic/coalescence collision fixes across all 53 commands, lazy on-demand open-vocabulary decoding (~4x speedup on standard commands), search query edge-case fixes, and system-wide audio/runtime hardening.
- **`v0.2.0` (2026-11-09)** — Hybrid constrained + open-vocabulary Kaldi ASR, dynamic Google & YouTube voice search, Christ University student portals (`CUE` & `KnowledgePro`), expanded 19-app Linux desktop suite (LibreOffice, VLC, GIMP, Krita, OBS, GNOME utilities), and PipeWire/WirePlumber (`wpctl`) audio controls.
- **`v0.1.0` (2026-11-08)** — Initial release featuring 16 kHz PCM capture, Silero VAD v5 ONNX engine, constrained-grammar Vosk ASR, $O(k)$ `CommandTrie` prefix matcher, 3-state execution engine, detached subprocess launcher, systemd user service, and universal multi-PC installer (`install.sh`).

---

## 9. Author & Contact

- **Author:** Mohammad Rayyan
- **Role:** Student at Christ University, Central Campus, Bangalore (Reg. No: `2641528`)
- **Email:** [mohammad.rayyan@bcah.christuniversity.in](mailto:mohammad.rayyan@bcah.christuniversity.in)
- **GitHub:** [https://github.com/rayyan-error](https://github.com/rayyan-error) (`@rayyan-error`)
- **LinkedIn:** [https://www.linkedin.com/in/rayyan-error](https://www.linkedin.com/in/rayyan-error) (`rayyan-error`)
