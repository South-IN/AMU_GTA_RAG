# AMU Admissions RAG

Human-validated retrieval pipeline for the AMU Guide to Admissions 2026-27.

## Current scope

- Preserve page layout, course fields and nested tables
- Normalize course records while retaining PDF provenance
- Create heading-aware policy chunks and normalized appendix rows
- Prepare extracted content for human approval before indexing
- Support exact facts and policy-oriented RAG queries

## Run with Docker

```bash
cp .env.example .env      # set GROQ_API_KEY and a long random POSTGRES_PASSWORD
docker compose up -d --build
```

Open <http://127.0.0.1:8501>. Compose starts three containers:

- `db`: PostgreSQL with pgvector, the system of record for the approved corpus
- `ingest`: a one-shot job that applies migrations, extracts the guide, applies the human-review batches in `reviews/` and loads only approved records
- `app`: the Streamlit chat interface, which reads from `db`

`ingest` skips work when the PDF, code, migrations and review batches are unchanged. Podman users can run the same file with `podman-compose`. See [docs/DOCKER.md](docs/DOCKER.md) for operations, migrations and troubleshooting.

## Human review

Extracted records start as `pending`. Approvals are applied from auditable review batches in `reviews/`, never by editing corpus JSON. Only approved records are indexed, and the database rejects any retrieval chunk that is not approved. To publish new approvals, add a batch file and run `docker compose up -d --build`.

A single batch can also be applied manually:

```bash
amu-apply-review --kind courses \
  --input data/review/guide-2026-27.course-corpus.pending.json \
  --decisions reviews/2026-10-07-course-sample.json \
  --output data/review/guide-2026-27.course-corpus.reviewed.json
```

## Local development

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
```

Without `AMU_RAG_DATABASE_URL`, commands read and write the JSON artifacts in `data/`. Build them with:

```bash
.venv/bin/amu-pipeline --no-database
```

Setting `AMU_RAG_DATABASE_URL` (for example to the Compose database on `127.0.0.1:5433`) makes the same commands use PostgreSQL.

The individual stages remain available as `amu-extract`, `amu-parse-courses`, `amu-parse-policies`, `amu-build-index`, `amu-load-index` and `amu-migrate`. See [docs/RETRIEVAL_INDEX.md](docs/RETRIEVAL_INDEX.md).

## Querying

Expand course abbreviations while preserving the rest of the query:

```bash
amu-query "Am I eligible for M.C.A.?"
```

See [docs/QUERY_PROCESSING.md](docs/QUERY_PROCESSING.md) for supported behavior and intent routing.

Run hybrid retrieval over the approved corpus:

```bash
amu-retrieve "What is the MCA age limit?" --limit 5
amu-retrieve "I have 12 Mathematics credits. Can I do MCA?" --limit 1 --llm-context
amu-retrieve "I completed B.Sc. Computer Science. Which courses can I apply for?" \
  --discover-courses --limit 5
```

The runner combines BM25, deterministic offline vectors and RRF, then hydrates the reviewed parent course. See [docs/HYBRID_RETRIEVAL.md](docs/HYBRID_RETRIEVAL.md).

Generate a grounded answer with Groq:

```bash
amu-answer "I have completed 12 credits in Mathematics. Can I do MCA?" --limit 1
```

The API key and model are read from `.env`; see [docs/ANSWER_GENERATION.md](docs/ANSWER_GENERATION.md).

Inside Docker, prefix any of these with `docker compose exec app`.

## Chat interface

The Streamlit UI provides linked in-text citations, page-labelled source cards, automatic course-discovery routing and guarded eligibility language. Outside Docker, run `.venv/bin/streamlit run streamlit_app.py`. See [docs/STREAMLIT_UI.md](docs/STREAMLIT_UI.md).

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full architecture and
[PHASE_LOG.md](PHASE_LOG.md) for implementation history.
