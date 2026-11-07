#!/usr/bin/env bash
""":"
# Python self-execution shim
exec "$(dirname "$0")/../.venv/bin/python" "$0" "$@"
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import AppConfig, Settings, config

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def find_desktop_binary(app_id: str) -> list[str]:
    """Scans system and user desktop files to find possible executable binaries."""
    search_dirs = [
        Path("/usr/share/applications"),
        Path.home() / ".local/share/applications",
        Path("/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local/share/flatpak/exports/share/applications",
    ]
    matches = []
    for d in search_dirs:
        if not d.is_dir():
            continue
        for desktop_file in d.glob("*.desktop"):
            if app_id in desktop_file.name.lower():
                try:
                    for line in desktop_file.read_text(errors="ignore").splitlines():
                        if line.startswith("Exec="):
                            cmd_part = line.split("=", 1)[1].strip()
                            bin_name = cmd_part.split()[0] if cmd_part else ""
                            bin_path = shutil.which(bin_name) or bin_name
                            if bin_path and bin_path not in matches:
                                matches.append(bin_path)
                            break
                except Exception:
                    continue
    return matches


def configure_apps(interactive: bool = False) -> dict:
    """Discovers and resolves binary paths for all supported apps."""
    print(f"\n{BOLD}{BLUE}===================================================================={RESET}")
    print(f"{BOLD}{BLUE}  Project Caramel / Uranus — Application Auto-Discovery & Config   {RESET}")
    print(f"{BOLD}{BLUE}===================================================================={RESET}\n")

    cfg = Settings()
    overrides = {}
    results = []

    for app_id, app in cfg.APPS.items():
        resolved = app.resolve_binary()
        
        # If not resolved via standard candidates, try searching desktop files
        if not resolved:
            extra_candidates = find_desktop_binary(app_id)
            for c in extra_candidates:
                if (os.path.isabs(c) and os.path.isfile(c) and os.access(c, os.X_OK)) or shutil.which(c):
                    resolved = c
                    break

        if interactive and not resolved:
            print(f"{YELLOW}[?] Application '{app.display_name}' ({app_id}) was not found in standard paths.{RESET}")
            resp = input(f"    Enter path to '{app.display_name}' executable (or press Enter to skip): ").strip()
            if resp:
                expanded = os.path.expanduser(resp)
                if (os.path.isabs(expanded) and os.path.isfile(expanded) and os.access(expanded, os.X_OK)) or shutil.which(expanded):
                    resolved = expanded
                    print(f"    {GREEN}Verified: {resolved}{RESET}")
                else:
                    print(f"    {RED}Warning: '{resp}' is not found or not executable. Skipping.{RESET}")

        if resolved:
            results.append((app.display_name, app_id, resolved, True))
            # Store override if path differs from default
            overrides[app_id] = {
                "display_name": app.display_name,
                "executable_path": resolved
            }
        else:
            results.append((app.display_name, app_id, "Not found (commands for this app will be disabled)", False))

    # Print summary table
    print(f"{'APPLICATION':<22} {'IDENTIFIER':<14} {'STATUS':<12} {'PATH'}")
    print("-" * 75)
    for name, aid, path, found in results:
        status_str = f"{GREEN}Available{RESET}" if found else f"{YELLOW}Optional{RESET}"
        path_str = path if found else f"{RED}{path}{RESET}"
        print(f"{name:<22} {aid:<14} {status_str:<21} {path_str}")

    config_path = PROJECT_ROOT / "config" / "local_apps.json"
    if overrides:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(overrides, f, indent=2)
        print(f"\n{GREEN}[OK] Local configuration written to:{RESET} {config_path}")
    else:
        print(f"\n{YELLOW}[!] No applications were discovered.{RESET}")

    print(f"{BOLD}{BLUE}===================================================================={RESET}\n")
    return overrides


def main():
    parser = argparse.ArgumentParser(description="Configure supported application paths for Project Caramel")
    parser.add_argument("--auto", action="store_true", help="Non-interactive automatic discovery")
    parser.add_argument("--interactive", "-i", action="store_true", help="Prompt for unconfigured or custom application paths")
    args = parser.parse_args()

    interactive_mode = args.interactive or (not args.auto and sys.stdin.isatty())
    configure_apps(interactive=interactive_mode)


if __name__ == "__main__":
    main()
