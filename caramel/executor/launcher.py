"""
Modular Application Launcher & Process Spawner for Project Caramel / Uranus.
Executes predefined, validated desktop applications without shell=True.
Detaches spawned processes in independent sessions.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time
from typing import Dict, List, Optional, Tuple

from config.settings import AppConfig, CommandDefinition, config


@dataclass(frozen=True)
class ExecutionResult:
    """Structured report returned after attempting command execution."""
    success: bool
    command_id: str
    target_app: str
    executed_args: List[str]
    message: str
    pid: Optional[int] = None
    execution_latency_ms: float = 0.0


class ApplicationLauncher:
    """
    Modular execution engine.
    Translates validated CommandDefinitions into safe detached system processes.
    Strictly avoids shell=True and arbitrary command execution.
    """
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def build_command_args(
        self,
        command: CommandDefinition,
        app_config: Optional[AppConfig] = None
    ) -> Tuple[bool, List[str], str]:
        """
        Compiles the exact argv argument list for a command definition.
        Supports standard desktop applications, web URLs, and SYSTEM_ACTION commands.
        Returns:
            (is_valid: bool, argv_list: List[str], error_message: str)
        """
        if command.action_type == "SYSTEM_ACTION":
            raw_args = command.extra_params.get("args", [])
            if not raw_args:
                return False, [], f"System command '{command.command_id}' has no executable args configured."
            bin_name = raw_args[0]
            resolved_bin = shutil.which(bin_name) if not os.path.isabs(bin_name) else bin_name
            if not self.dry_run:
                is_valid_bin = False
                if resolved_bin:
                    if os.path.isabs(resolved_bin) and os.path.isfile(resolved_bin) and os.access(resolved_bin, os.X_OK):
                        is_valid_bin = True
                    elif shutil.which(resolved_bin):
                        is_valid_bin = True
                if not is_valid_bin:
                    return False, [], f"System binary '{bin_name}' not found or not executable."
            final_args = [resolved_bin or bin_name] + list(raw_args[1:])
            return True, final_args, ""

        app = app_config or config.get_app(command.target_app)
        if not app:
            return False, [], f"Target application '{command.target_app}' is not registered in configuration."

        resolved_bin = app.resolve_binary()
        if not resolved_bin:
            # In dry-run mode, if binary is not installed on this specific environment,
            # allow testing argument construction using the configured path string.
            if self.dry_run:
                resolved_bin = app.executable_path
            else:
                return (
                    False,
                    [],
                    f"Executable for '{app.display_name}' not found or not executable at '{app.executable_path}'."
                )

        args = [resolved_bin]
        args.extend(app.default_args)

        if command.new_window:
            args.extend(app.new_window_args)

        if command.url:
            args.extend(app.url_args)
            args.append(command.url)

        return True, args, ""

    def execute(
        self,
        command: CommandDefinition,
        app_config: Optional[AppConfig] = None
    ) -> ExecutionResult:
        """
        Spawns the target desktop application in a detached session.
        Never blocks the agent or child processes.
        """
        t0 = time.perf_counter()

        is_valid, argv, err_msg = self.build_command_args(command, app_config)
        if not is_valid:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=False,
                command_id=command.command_id,
                target_app=command.target_app,
                executed_args=[],
                message=err_msg,
                pid=None,
                execution_latency_ms=latency_ms
            )

        if self.dry_run:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=True,
                command_id=command.command_id,
                target_app=command.target_app,
                executed_args=argv,
                message=f"[DRY RUN] Built verified argv: {argv}",
                pid=None,
                execution_latency_ms=latency_ms
            )

        try:
            # Spawn detached process in a new session group (setsid)
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=True,
                command_id=command.command_id,
                target_app=command.target_app,
                executed_args=argv,
                message=f"Successfully spawned '{command.target_app}' (PID: {proc.pid})",
                pid=proc.pid,
                execution_latency_ms=latency_ms
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=False,
                command_id=command.command_id,
                target_app=command.target_app,
                executed_args=argv,
                message=f"Process spawn failed: {exc}",
                pid=None,
                execution_latency_ms=latency_ms
            )
