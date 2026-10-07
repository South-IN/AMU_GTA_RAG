# AMU Admissions RAG

Human-validated retrieval pipeline for the AMU Guide to Admissions 2026-27.

## Current scope

- Preserve page layout, course fields and nested tables
- Normalize course records while retaining PDF provenance
- Create heading-aware policy chunks and normalized appendix rows
- Prepare extracted content for human approval before indexing
- Support exact facts and policy-oriented RAG queries

## Development

```powershell
$python = "C:\Users\gtx25\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $python -m unittest discover -s tests -v
```

Build the pending policy and appendix corpus from the full extraction:

```powershell
$env:PYTHONPATH = "src"
& $python -m amu_admissions_rag.policy_cli
```

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full architecture and
[PHASE_LOG.md](PHASE_LOG.md) for implementation history.
