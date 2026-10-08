# Published corpus

This directory contains the generated, human-approved corpus for the complete
**AMU Guide to Admissions 2026-27**.

| File | Purpose | Records |
|---|---|---:|
| `guide-2026-27.human-review.json` | Metadata-light course content for manual inspection | 179 courses |
| `guide-2026-27.course-corpus.reviewed.json` | Canonical reviewed course records with page provenance | 179 courses |
| `guide-2026-27.policy-corpus.reviewed.json` | Canonical reviewed guide policies and appendix rows | 154 sections + 1,390 rows |
| `guide-2026-27.index-corpus.approved.json` | Self-contained chunks consumed by retrieval | 1,723 chunks |

All records were rebuilt from the repository PDF and passed through the review
decisions in `reviews/`. The application still loads the approved index into
PostgreSQL/pgvector during ingestion; these files provide an inspectable and
versioned snapshot of that input.

The `human-review` export omits extraction geometry such as bounding boxes.
The canonical files retain source-page provenance and technical identifiers
needed for reproducible citations and database loading.
