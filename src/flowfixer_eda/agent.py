from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import Patch, ProposalBackend, Task, VerificationResult, Verifier
from .parser import parse_log
from .retrieval import retrieve
from .validator import PatchRejected, apply_patch, validate_patch


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
        seen: set[str] = set()
        valid = 0
        generated = 0
        last = VerificationResult(False, False, "repair budget exhausted")
        diagnosis_correct = False
        for attempt in range(1, self.max_attempts + 1):
            patch: Patch = self.backend.propose(task, diagnostic, retrieved, feedback)
            generated += 1
            diagnosis_correct = diagnosis_correct or patch.category == task.category
            with tempfile.TemporaryDirectory(prefix=f"flowfixer-{task.task_id}-") as temp:
                candidate = Path(temp) / "workspace"
                shutil.copytree(source_workspace, candidate)
                try:
                    fingerprint = validate_patch(task, patch, candidate, seen)
                    seen.add(fingerprint)
                    valid += 1
                    apply_patch(patch, candidate)
                except PatchRejected as exc:
                    feedback.append(f"validator rejected candidate: {exc}")
                    continue
                last = self.verifier.verify(task, candidate, patch.restart_stage)
                if last.flow_complete and last.quality_pass:
                    return RepairOutcome(task.task_id, attempt, diagnosis_correct, valid, generated, last)
                feedback.append(last.feedback)
        return RepairOutcome(task.task_id, self.max_attempts, diagnosis_correct, valid, generated, last)

