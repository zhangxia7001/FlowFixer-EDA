from __future__ import annotations

import re

from .models import DiagnosticRecord

_FATAL = re.compile(r"(?:fatal|error|failed|violation)", re.IGNORECASE)
_WARNING = re.compile(r"warn(?:ing)?", re.IGNORECASE)
_FILE = re.compile(r"[A-Za-z0-9_./-]+\.(?:v|sv|sdc|tcl|json|log|rpt)")
_METRIC = re.compile(r"\b(WNS|TNS|AREA|POWER)\s*[:=]\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_log(log: str, failed_stage: str, limit: int = 12) -> DiagnosticRecord:
    lines = [line.strip() for line in log.splitlines() if line.strip()]
    fatal = tuple(line for line in lines if _FATAL.search(line))[:limit]
    warnings = tuple(line for line in lines if _WARNING.search(line))[:limit]
    files = tuple(dict.fromkeys(match.group(0) for match in _FILE.finditer(log)))
    metrics = {match.group(1).upper(): float(match.group(2)) for match in _METRIC.finditer(log)}
    return DiagnosticRecord(failed_stage, fatal, warnings, files, metrics)

