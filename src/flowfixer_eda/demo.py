from __future__ import annotations

from pathlib import Path

from .models import DiagnosticRecord, Patch, Task, VerificationResult


class ReferencePatchBackend:
    """Deterministic dataset backend; replace with an LLM for real experiments."""

    def propose(self, task: Task, diagnostic: DiagnosticRecord, retrieved: list[str], feedback_history: list[str]) -> Patch:
        return task.reference_patch


class ContractVerifier:
    """Checks task expected files and declared quality gates."""

    def verify(self, task: Task, workspace: Path, restart_stage: str) -> VerificationResult:
        mismatches: list[str] = []
        for name, expected in task.expected_files.items():
            target = workspace / name
            actual = target.read_text(encoding="utf-8") if target.exists() else "<missing>"
            if actual != expected:
                mismatches.append(name)
        flow_complete = not mismatches
        gates = dict(task.quality_gates) if flow_complete else {name: False for name in task.quality_gates}
        quality_pass = flow_complete and all(gates.values())
        feedback = "all verification gates passed" if quality_pass else f"mismatched files: {mismatches}"
        return VerificationResult(flow_complete, quality_pass, feedback, gates)
