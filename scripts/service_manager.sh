#!/usr/bin/env bash
# Service manager script for Project Caramel / Uranus (User systemd)
set -e

SERVICE_NAME="caramel.service"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_SRC="/home/rayyan-error/Projects/Uranus/systemd/${SERVICE_NAME}"

case "$1" in
    install)
        echo "Installing ${SERVICE_NAME} to ${USER_SYSTEMD_DIR}..."
        mkdir -p "${USER_SYSTEMD_DIR}"
        cp "${SERVICE_SRC}" "${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
        systemctl --user daemon-reload
        systemctl --user enable "${SERVICE_NAME}"
        echo "Service installed and enabled for user login autostart."
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
