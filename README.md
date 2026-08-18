# FlowFixer-EDA

This package implements the core FlowFixer-EDA workflow and provides a
minimal sample dataset covering eight RTL-to-GDS error categories.

## Contents

- Stage-aware log parsing and lightweight knowledge retrieval
- Structured patch generation with five deterministic operations
- File-scope, applicability, overlap, repetition, and safety validation
- Tool-feedback repair loop and evaluation metrics
- Disposable checkpoint workspaces and trusted EDA command adapters
- JSON patch schema: `schemas/patch.schema.json`
- Minimal sample dataset with eight tasks: `dataset/tasks.json`
- Automated tests: `tests/test_artifact.py`

## Quick start

Python 3.10 or newer is required. The package has no runtime dependencies.

```powershell
$env:PYTHONPATH = "src"
python -m flowfixer_eda.cli list --dataset dataset/tasks.json
python -m flowfixer_eda.cli demo --dataset dataset/tasks.json --output runs/demo
python -m unittest discover -s tests -v
```

Each task contains faulty inputs, a diagnostic log, the error category,
the failed flow stage, a verified reference patch, and quality-gate results.

## Requirements

Third-party EDA tools, PDK files, model weights, and official manuals remain
subject to their respective licenses and should be obtained from their
official sources when needed.

## License

MIT License.
