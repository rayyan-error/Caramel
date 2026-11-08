#!/usr/bin/env bash
# Service manager script for Project Caramel / Uranus (User systemd)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="caramel.service"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_SRC="${PROJECT_ROOT}/systemd/${SERVICE_NAME}"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
PORTAUDIO_PATH="${PROJECT_ROOT}/.venv/lib/portaudio/libportaudio.so.2"

case "$1" in
    install)
        echo "Installing ${SERVICE_NAME} for user $(whoami) to ${USER_SYSTEMD_DIR}..."
        mkdir -p "${USER_SYSTEMD_DIR}"
        # Dynamically substitute paths for the current machine and clone location
        sed \
            -e "s|WorkingDirectory=.*|WorkingDirectory=${PROJECT_ROOT}|g" \
            -e "s|ExecStart=.*|ExecStart=${PYTHON_BIN} ${PROJECT_ROOT}/run.py|g" \
            -e "s|Environment=PORTAUDIO_PATH=.*|Environment=PORTAUDIO_PATH=${PORTAUDIO_PATH}|g" \
            "${SERVICE_SRC}" > "${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
        systemctl --user daemon-reload
        systemctl --user enable "${SERVICE_NAME}"
        mkdir -p "${HOME}/.local/bin"
        ln -sf "${PROJECT_ROOT}/scripts/caramel" "${HOME}/.local/bin/caramel"
        echo "Service installed and enabled for user login autostart."
        echo "CLI command 'caramel' linked to ${HOME}/.local/bin/caramel."
        echo "To restart anytime, run: caramel restart"
        echo "To start immediately, run: $0 start"
        ;;
    start)
        echo "Starting ${SERVICE_NAME}..."
        systemctl --user start "${SERVICE_NAME}"
        systemctl --user status "${SERVICE_NAME}" --no-pager
        ;;
    stop)
        echo "Stopping ${SERVICE_NAME}..."
        systemctl --user stop "${SERVICE_NAME}"
        ;;
    restart)
        echo "Restarting ${SERVICE_NAME}..."
        systemctl --user restart "${SERVICE_NAME}"
        ;;
    status)
        systemctl --user status "${SERVICE_NAME}" --no-pager
        ;;
    logs)
        journalctl --user-u "${SERVICE_NAME}" -f
        ;;
    uninstall)
        echo "Uninstalling ${SERVICE_NAME}..."
        systemctl --user stop "${SERVICE_NAME}" || true
        systemctl --user disable "${SERVICE_NAME}" || true
        rm -f "${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
        systemctl --user daemon-reload
        echo "Service uninstalled."
        ;;
    *)
        echo "Usage: $0 {install|start|stop|restart|status|logs|uninstall}"
        exit 1
        ;;
esac
