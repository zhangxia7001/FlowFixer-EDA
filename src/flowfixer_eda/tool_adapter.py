from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import Task, VerificationResult


@dataclass(frozen=True)
class CommandSpec:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: int = 1800


class CommandVerifier:
    """Run trusted, administrator-supplied EDA and quality commands without a shell."""

    def __init__(
        self,
        stage_commands: dict[str, tuple[CommandSpec, ...]],
        quality_commands: tuple[CommandSpec, ...],
    ) -> None:
        self.stage_commands = stage_commands
        self.quality_commands = quality_commands

    @staticmethod
    def _run(command: CommandSpec, workspace: Path) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                list(command.argv),
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=command.timeout_seconds,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"{command.name}: {exc}"
        output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        message = f"{command.name}: exit={result.returncode}"
        if output:
            message += f"\n{output[-4000:]}"
        return result.returncode == 0, message

    def verify(self, task: Task, workspace: Path, rerun_stage: str) -> VerificationResult:
        commands = self.stage_commands.get(rerun_stage)
        if not commands:
            return VerificationResult(False, False, f"no trusted tool command for stage: {rerun_stage}")

        flow_messages: list[str] = []
        for command in commands:
            passed, message = self._run(command, workspace)
            flow_messages.append(message)
            if not passed:
                return VerificationResult(False, False, "\n".join(flow_messages))

        gates: dict[str, bool] = {}
        quality_messages: list[str] = []
        for command in self.quality_commands:
            passed, message = self._run(command, workspace)
            gates[command.name] = passed
            quality_messages.append(message)
        quality_pass = bool(gates) and all(gates.values())
        feedback = "\n".join((*flow_messages, *quality_messages))
        return VerificationResult(True, quality_pass, feedback, gates)
