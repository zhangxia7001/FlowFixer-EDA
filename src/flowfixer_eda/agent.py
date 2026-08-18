from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import Patch, ProposalBackend, Task, VerificationResult, Verifier
from .parser import parse_log
from .retrieval import retrieve
from .sandbox import sandbox_workspace
from .validator import PatchRejected, apply_patch, patch_fingerprint, validate_patch


@dataclass(frozen=True)
class RepairOutcome:
    task_id: str
    attempts: int
    diagnosis_correct: bool
    valid_patches: int
    generated_patches: int
    result: VerificationResult


class FlowFixerAgent:
    def __init__(self, backend: ProposalBackend, verifier: Verifier, corpus_path: str | Path, max_attempts: int = 5):
        self.backend = backend
        self.verifier = verifier
        self.corpus_path = Path(corpus_path)
        self.max_attempts = max_attempts

    def repair(self, task: Task, source_workspace: Path) -> RepairOutcome:
        diagnostic = parse_log(task.log, task.failed_stage)
        retrieved = retrieve(diagnostic, self.corpus_path)
        feedback: list[str] = []
        rejected: dict[str, str] = {}
        valid = 0
        generated = 0
        last = VerificationResult(False, False, "repair budget exhausted")
        diagnosis_correct = False
        for attempt in range(1, self.max_attempts + 1):
            patch: Patch = self.backend.propose(task, diagnostic, retrieved, feedback)
            generated += 1
            diagnosis_correct = diagnosis_correct or patch.error_category == task.error_category
            fingerprint = patch_fingerprint(patch)
            if fingerprint in rejected:
                feedback.append(f"repeated patch rejected: {rejected[fingerprint]}")
                continue
            with sandbox_workspace(source_workspace) as candidate:
                try:
                    validate_patch(task, patch, candidate, rejected)
                    valid += 1
                    apply_patch(patch, candidate)
                except (PatchRejected, OSError, ValueError) as exc:
                    reason = f"validator or application rejected candidate: {exc}"
                    rejected[fingerprint] = reason
                    feedback.append(reason)
                    continue
                last = self.verifier.verify(task, candidate, patch.rerun_stage)
                if last.flow_complete and last.quality_pass:
                    return RepairOutcome(task.task_id, attempt, diagnosis_correct, valid, generated, last)
                rejected[fingerprint] = last.feedback
                feedback.append(last.feedback)
        return RepairOutcome(task.task_id, self.max_attempts, diagnosis_correct, valid, generated, last)
