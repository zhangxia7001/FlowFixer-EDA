from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _copy_git_checkpoint(source: Path, candidate: Path, archive: Path) -> bool:
    try:
        root = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

    if Path(root).resolve() != source.resolve():
        raise ValueError("a Git-backed source workspace must be supplied at its repository root")
    try:
        status = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if status.strip():
            raise ValueError("Git-backed source workspace must be clean before sandbox creation")
        subprocess.run(
            ["git", "-C", str(source), "archive", "--format=tar", f"--output={archive}", "HEAD"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"failed to materialize clean Git checkpoint: {exc}") from exc

    candidate.mkdir(parents=True, exist_ok=True)
    root_resolved = candidate.resolve()
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            destination = (candidate / member.name).resolve()
            if not destination.is_relative_to(root_resolved):
                raise ValueError(f"unsafe Git archive member: {member.name}")
        bundle.extractall(candidate)
    return True


@contextmanager
def sandbox_workspace(source_workspace: Path) -> Iterator[Path]:
    """Create a disposable candidate workspace from a clean checkpoint or snapshot."""

    with tempfile.TemporaryDirectory(prefix="flowfixer-sandbox-") as temp:
        temp_root = Path(temp)
        candidate = temp_root / "workspace"
        archive = temp_root / "checkpoint.tar"
        if not _copy_git_checkpoint(source_workspace, candidate, archive):
            shutil.copytree(source_workspace, candidate)
        yield candidate
