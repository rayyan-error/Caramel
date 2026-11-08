#!/usr/bin/env bash
# ==============================================================================
# Project Caramel / Uranus — Universal Linux Installer
# Automated setup for system packages, Python venv, offline AI models,
# application path autodetection, and optional systemd startup service.
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# ANSI Colors
GREEN="\033[92m"
YELLOW="\033[93m"
RED="\033[91m"
BLUE="\033[94m"
BOLD="\033[1m"
RESET="\033[0m"

NON_INTERACTIVE=false
SKIP_MODELS=false
SKIP_SERVICE=false

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -y|--yes) NON_INTERACTIVE=true; shift ;;
        --skip-models) SKIP_MODELS=true; shift ;;
        --skip-service) SKIP_SERVICE=true; shift ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "  -y, --yes          Non-interactive mode (accept defaults)"
            echo "  --skip-models      Skip downloading offline AI models"
            echo "  --skip-service     Do not prompt to configure systemd autostart"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${BOLD}${BLUE}====================================================================${RESET}"
echo -e "${BOLD}${BLUE}   Project Caramel / Uranus — Linux Environment Installer         ${RESET}"
echo -e "${BOLD}${BLUE}====================================================================${RESET}\n"

# ------------------------------------------------------------------------------
# 1. System Package Management & Capability Checks
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/6] Checking system capabilities & dependencies...${RESET}"

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[ERROR] python3 is not installed. Please install Python 3.10+ first.${RESET}"
    exit 1
fi

MISSING_DEPS=()

# Check venv capability
if ! python3 -c "import venv" &>/dev/null; then
    MISSING_DEPS+=("python3-venv")
fi

# Check download utilities
if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
    MISSING_DEPS+=("curl")
fi

if ! command -v unzip &>/dev/null; then
    MISSING_DEPS+=("unzip")
fi

# Check PortAudio & espeak
HAS_PORTAUDIO=$(python3 -c "import ctypes.util; print(bool(ctypes.util.find_library('portaudio')))" 2>/dev/null || echo "False")
HAS_ESPEAK=$(python3 -c "import ctypes.util; print(bool(ctypes.util.find_library('espeak-ng')))" 2>/dev/null || echo "False")

if [ "$HAS_PORTAUDIO" != "True" ] && [ ! -f "${SCRIPT_DIR}/.venv/lib/portaudio/libportaudio.so.2" ]; then
    MISSING_DEPS+=("libportaudio2")
fi

if [ "$HAS_ESPEAK" != "True" ]; then
    MISSING_DEPS+=("libespeak-ng1")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo -e "${YELLOW}[!] Recommended system packages not found:${RESET} ${MISSING_DEPS[*]}"
    
    # Try detecting package manager
    PKG_CMD=""
    if command -v apt-get &>/dev/null; then
        PKG_CMD="sudo apt-get install -y ${MISSING_DEPS[*]}"
    elif command -v dnf &>/dev/null; then
        PKG_CMD="sudo dnf install -y ${MISSING_DEPS[*]}"
    elif command -v pacman &>/dev/null; then
        PKG_CMD="sudo pacman -S --noconfirm ${MISSING_DEPS[*]}"
    fi

    if [ -n "$PKG_CMD" ]; then
        if [ "$NON_INTERACTIVE" = true ]; then
            echo -e "Attempting non-interactive install: ${PKG_CMD}"
            eval "$PKG_CMD" 2>/dev/null || echo -e "${YELLOW}[!] Sudo not available without password. Proceeding with user-level installation...${RESET}"
        else
            read -rp "Would you like to install them via sudo? [Y/n] " prompt_install
            prompt_install=${prompt_install:-Y}
            if [[ "$prompt_install" =~ ^[Yy]$ ]]; then
                eval "$PKG_CMD" || echo -e "${YELLOW}[!] System install encountered an error. Proceeding...${RESET}"
            fi
        fi
    fi
else
    echo -e "${GREEN}[OK] Core system dependencies verified.${RESET}"
fi

# ------------------------------------------------------------------------------
# 2. Python Virtual Environment (.venv)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[2/6] Setting up Python virtual environment...${RESET}"
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
else
    echo -e "${GREEN}[OK] Existing virtual environment detected (.venv).${RESET}"
fi

VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"
VENV_PIP="${SCRIPT_DIR}/.venv/bin/pip"

echo "Upgrading pip and installing Python dependencies..."
"${VENV_PIP}" install --upgrade pip --quiet
"${VENV_PIP}" install -r requirements.txt --quiet
echo -e "${GREEN}[OK] Python packages installed.${RESET}"

# ------------------------------------------------------------------------------
# 3. PortAudio Library Setup
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[3/6] Verifying audio backend (PortAudio / PipeWire)...${RESET}"
mkdir -p "${SCRIPT_DIR}/.venv/lib/portaudio"

# Check if sounddevice can find PortAudio
PA_TEST=$("${VENV_PYTHON}" -c "
import sounddevice as sd
print('OK')
" 2>&1 || true)

if [[ "$PA_TEST" == *"OK"* ]]; then
    echo -e "${GREEN}[OK] PortAudio is accessible to Python sounddevice.${RESET}"
else
    echo -e "${YELLOW}[!] Locating system libportaudio.so.2...${RESET}"
    SYS_PA=$(ldconfig -p 2>/dev/null | grep 'libportaudio.so.2' | awk '{print $NF}' | head -n 1 || true)
    if [ -n "$SYS_PA" ] && [ -f "$SYS_PA" ]; then
        ln -sf "$SYS_PA" "${SCRIPT_DIR}/.venv/lib/portaudio/libportaudio.so.2"
        echo -e "${GREEN}[OK] Linked system PortAudio from ${SYS_PA}.${RESET}"
    else
        echo -e "${YELLOW}[!] Fallback to pre-bundled local portaudio library if available.${RESET}"
    fi
fi

# ------------------------------------------------------------------------------
# 4. Offline AI Models (Silero VAD + Vosk)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[4/6] Verifying offline speech & VAD models...${RESET}"
if [ "$SKIP_MODELS" = false ]; then
    "${VENV_PYTHON}" scripts/download_models.py
    echo -e "${GREEN}[OK] Offline AI models ready.${RESET}"
else
    echo "Skipping models download as requested."
fi

# ------------------------------------------------------------------------------
# 5. Application Path Auto-Discovery
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[5/6] Auto-detecting desktop applications on this PC...${RESET}"
if [ "$NON_INTERACTIVE" = true ]; then
    "${VENV_PYTHON}" scripts/configure_apps.py --auto
else
    "${VENV_PYTHON}" scripts/configure_apps.py --interactive
fi

# ------------------------------------------------------------------------------
# 6. Self-Diagnostic Test Suite
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[6/6] Running system verification tests...${RESET}"
"${VENV_PYTHON}" tests/test_part1_config.py >/dev/null && echo -e "  [✓] Configuration & dynamic grammar"
"${VENV_PYTHON}" tests/test_part4_trie_matcher.py >/dev/null && echo -e "  [✓] Prefix-tree command matching"
"${VENV_PYTHON}" tests/test_part5_launcher.py >/dev/null && echo -e "  [✓] Process execution & argument compilation"
"${VENV_PYTHON}" tests/test_v02_features.py >/dev/null && echo -e "  [✓] Version 0.2 features (search, portals, apps, volume)"

echo -e "\n${BOLD}${GREEN}====================================================================${RESET}"
echo -e "${BOLD}${GREEN}  Project Caramel / Uranus successfully installed and ready!        ${RESET}"
echo -e "${BOLD}${GREEN}====================================================================${RESET}\n"

# ------------------------------------------------------------------------------
# Optional: Setup systemd login autostart & CLI shortcut
# ------------------------------------------------------------------------------
mkdir -p "${HOME}/.local/bin"
ln -sf "${PROJECT_ROOT}/scripts/caramel" "${HOME}/.local/bin/caramel"

if [ "$SKIP_SERVICE" = false ]; then
    if [ "$NON_INTERACTIVE" = true ]; then
        ./scripts/service_manager.sh install
    else
        read -rp "Would you like Caramel to start automatically on login? [Y/n] " prompt_service
        prompt_service=${prompt_service:-Y}
        if [[ "$prompt_service" =~ ^[Yy]$ ]]; then
            ./scripts/service_manager.sh install
            read -rp "Start the background service right now? [Y/n] " prompt_start
            prompt_start=${prompt_start:-Y}
            if [[ "$prompt_start" =~ ^[Yy]$ ]]; then
                ./scripts/service_manager.sh start
            fi
        fi
    fi
fi

echo -e "\nTo manage the Caramel service from any terminal:"
echo -e "  ${BOLD}caramel restart${RESET}   (Restart the background service)"
echo -e "  ${BOLD}caramel status${RESET}    (Check service health and logs)"
echo -e "  ${BOLD}caramel logs${RESET}      (Stream live background logs)"
echo -e "\nTo test Caramel manually in the foreground:"
echo -e "  ${BOLD}caramel --dry-run${RESET}"
echo -e "  ${BOLD}caramel run${RESET}\n"
