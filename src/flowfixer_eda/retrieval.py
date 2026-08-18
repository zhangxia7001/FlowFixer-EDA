from __future__ import annotations

import json
import re
from pathlib import Path

from .models import DiagnosticRecord


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def retrieve(record: DiagnosticRecord, corpus_path: str | Path, top_k: int = 3) -> list[str]:
    chunks = json.loads(Path(corpus_path).read_text(encoding="utf-8"))["chunks"]
    query = _tokens(" ".join((record.stage, *record.fatal_lines, *record.warning_lines)))
    ranked = sorted(
        chunks,
        key=lambda chunk: (len(query & _tokens(chunk["text"])), chunk["id"]),
        reverse=True,
    )
    return [str(chunk["text"]) for chunk in ranked[:top_k]]

