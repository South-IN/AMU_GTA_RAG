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
python -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -e .
& $python -m unittest discover -s tests -v
```

Build the pending policy and appendix corpus from the full extraction:

```powershell
$env:PYTHONPATH = "src"
& $python -m amu_admissions_rag.policy_cli
```

Build an approval-gated retrieval corpus:

```powershell
$env:PYTHONPATH = "src"
& $python -m amu_admissions_rag.index_cli
```

Use `--include-pending` only for a local chunk preview. PostgreSQL loading requires approved records and `AMU_RAG_DATABASE_URL`; see [docs/RETRIEVAL_INDEX.md](docs/RETRIEVAL_INDEX.md).

Human approvals are applied from an auditable review batch rather than by editing corpus JSON manually:

```powershell
& $python -m amu_admissions_rag.apply_review_cli `
  --kind courses `
  --input data/review/guide-2026-27.course-corpus.pending.json `
  --decisions reviews/2026-10-07-course-sample.json `
  --output data/review/guide-2026-27.course-corpus.reviewed.json
```

Expand course abbreviations while preserving the rest of the query:

```powershell
& $python -m amu_admissions_rag.query_cli "Am I eligible for M.C.A.?"
```

See [docs/QUERY_PROCESSING.md](docs/QUERY_PROCESSING.md) for supported behavior and intent routing.

Run hybrid retrieval over the approved corpus:

```powershell
& $python -m amu_admissions_rag.retrieval_cli "What is the MCA age limit?" --limit 5
& $python -m amu_admissions_rag.retrieval_cli `
  "I have 12 Mathematics credits. Can I do MCA?" `
  --limit 1 --llm-context
& $python -m amu_admissions_rag.retrieval_cli `
  "I completed B.Sc. Computer Science. Which courses can I apply for?" `
  --discover-courses --limit 5
```

The local runner combines BM25, deterministic offline vectors and RRF, then hydrates the reviewed parent course. See [docs/HYBRID_RETRIEVAL.md](docs/HYBRID_RETRIEVAL.md).

Generate a grounded answer for any course in the approved guide corpus with Groq:

```powershell
& $python -m amu_admissions_rag.answer_cli `
  "I have completed 12 credits in Mathematics. Can I do MCA?" `
  --limit 1
```

The API key and model are read from the ignored `.env`; see [docs/ANSWER_GENERATION.md](docs/ANSWER_GENERATION.md).

Launch the Streamlit chat interface:

```powershell
$env:PYTHONPATH = "src"
& $python -m streamlit run streamlit_app.py
```

The UI provides linked in-text citations, page-labelled source cards, automatic course-discovery routing and guarded eligibility language. See [docs/STREAMLIT_UI.md](docs/STREAMLIT_UI.md).

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full architecture and
[PHASE_LOG.md](PHASE_LOG.md) for implementation history.
