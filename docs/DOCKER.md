# Docker Deployment

The project runs as a Compose stack with separate containers for the database and the app. PostgreSQL is the system of record for the approved corpus.

## Services

| Service | Image | Role |
|---|---|---|
| `db` | `pgvector/pgvector:pg17` | PostgreSQL with pgvector; data in the `db-data` volume |
| `ingest` | `amu-admissions-rag` | One-shot job: migrations, then the full ingestion pipeline and an atomic load |
| `app` | `amu-admissions-rag` | Streamlit chat UI; reads the approved corpus from `db` |

Startup order is enforced with health checks: `db` healthy → `ingest` completes successfully → `app` starts.

```text
reviews/*.json ─┐
guide PDF ──────┼─► ingest: extract → parse (pending) → apply review batches → approved index
                │                                                         │
                │                         migrations + atomic replace ◄──┘
                ▼
               db (documents, course_records, policy_sections, appendix_records,
                   retrieval_chunks + tsvector + pgvector, ingestion_runs, schema_migrations)
                ▼
               app: load approved corpus → hybrid retrieval → Groq → cited answer
```

## First run

```bash
cp .env.example .env      # then set GROQ_API_KEY and a long random POSTGRES_PASSWORD
docker compose up -d --build
```

Open <http://127.0.0.1:8501>. The first ingestion extracts all 187 pages and takes about a minute; `docker compose logs -f ingest` shows progress.

With Podman, use `podman-compose` in place of `docker compose`; the same `compose.yaml` works with both.

Ports are bound to `127.0.0.1` only. Override them with `AMU_APP_HOST_PORT` (default 8501) and `AMU_DB_HOST_PORT` (default 5433) in `.env`.

## Human review stays the ingestion gate

`ingest` loads only records approved in a review batch under `reviews/`. Pending and rejected records never reach `retrieval_chunks`, and the database enforces this with a `CHECK (review_status = 'approved')` constraint.

To publish new approvals, add a batch file to `reviews/` and rebuild:

```bash
docker compose up -d --build
```

Batches are applied oldest first by `reviewed_at`, so later decisions override earlier ones. Each decision is routed to the course or policy corpus that owns its record ID, and an unknown ID fails the run without changing the database.

## Change detection

Every load records a row in `ingestion_runs` with a fingerprint of the source PDF, the package code, the SQL migrations and every review batch. When nothing has changed, `ingest` applies pending migrations and exits in a few seconds. To force a rebuild:

```bash
docker compose run --rm ingest amu-pipeline --force
```

## Migrations

Schema changes live in `sql/NNN_description.sql` and are applied in order by `amu-migrate` (also run by `ingest`). The runner:

- records each migration's name and SHA-256 checksum in `schema_migrations`;
- applies each pending migration in its own transaction;
- takes a PostgreSQL advisory lock so concurrent runners cannot race;
- refuses to continue if an already-applied migration file has been edited.

Never edit an applied migration; add a new numbered file instead. Migration files must not contain their own `BEGIN`/`COMMIT`.

## Common operations

```bash
docker compose logs -f app                       # app logs
docker compose run --rm ingest amu-migrate       # migrations only
docker compose exec app amu-evaluate-retrieval   # retrieval evaluation against the database
docker compose exec app python -m unittest discover -s tests
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose down                              # stop; data is kept
docker compose down -v                           # stop and delete the database and artifacts
```

## Database integration tests

The PostgreSQL round-trip tests are skipped unless `AMU_RAG_TEST_DATABASE_URL` is set. Run them against a separate, disposable database:

```bash
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" amu_test'
set -a; . ./.env; set +a
AMU_RAG_TEST_DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@127.0.0.1:5433/amu_test" \
  .venv/bin/python -m unittest tests.test_postgres_integration -v
```

## Local development without Docker

When `AMU_RAG_DATABASE_URL` is unset, every command falls back to the JSON artifacts in `data/`. `amu-pipeline` builds them without a database:

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/amu-pipeline --no-database
.venv/bin/streamlit run streamlit_app.py
```

To run host-side tools against the Compose database instead, export `AMU_RAG_DATABASE_URL=postgresql://<user>:<password>@127.0.0.1:5433/<db>`.

## Retrieval in the database

The app rebuilds the approved index from PostgreSQL losslessly, including chunk order, source provenance and review metadata, and ranks it with the same `HybridRetriever` used offline. Answers therefore match the evaluated local pipeline exactly. The loader also stores 1024-dimension embeddings, so the SQL `hybrid_search_chunks` function is usable for direct database search. Moving ranking into SQL is a separate step, because PostgreSQL full-text ranking differs from the evaluated BM25.
