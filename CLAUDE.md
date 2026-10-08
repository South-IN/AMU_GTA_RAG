# CLAUDE.md

RAG assistant for the AMU Guide to Admissions 2026-27 (`guide_to_admission_2026_27.pdf`). Architecture, history and operations live in `README.md`, `PHASE_LOG.md` (phases 1-13) and `docs/` — read those first.

## Where we are (2026-10-08)

- **Runs in Docker** (`compose.yaml`): `db` (Postgres 17 + pgvector), one-shot `ingest` (migrations → extract → parse → apply `reviews/*.json` → load), `app` (Streamlit, 127.0.0.1:8501). This machine uses Podman: always `podman-compose up -d --build --force-recreate`, otherwise containers keep the old image.
- **Corpus is fresh, nothing approved.** All earlier approvals, data and Docker volumes were wiped. 189 courses, 114 policy chunks and 1,390 appendix rows are parsed and pending; the app answers "evidence is insufficient" until review is done.
- **Next step: the user is doing human review.** Worksheets are in `data/review/` (gitignored): `worksheet.15-courses.json`, `worksheet.policy-sections.json`, and `review-batch.template.json` (67 decisions, status `TODO`). The finished batch goes in `reviews/`, then rebuild the stack.
- **Branches:** `main` is behind. `chore/fresh-corpus` holds the PDF rename, the parser fixes and the fresh-corpus reset, and has not been merged yet; confirm with the user before merging.

## Gotchas

- Human approval is the ingestion gate: never edit corpus JSON or hand-write approvals. Approvals only come from batches the user creates.
- Ranking stays in `HybridRetriever`; Postgres is the store. The retrieval evaluations (16/16, 5/5) only pass once the 15 sample courses in `docs/HUMAN_VALIDATION_COURSES.md` are approved.
- Known parser remainder: the course-type key on page 37 is filed under "Refund of fee".
- `ruff` has about 51 pre-existing findings; only keep new code clean.
