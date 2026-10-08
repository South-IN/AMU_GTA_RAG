# Retrieval Index Design

## Scope

Phase 6 converts reviewed records into complete information chunks and defines the PostgreSQL storage and hybrid-ranking layer. It does not add a graph database or choose an embedding provider.

## Approval Gate

- Approved records become index chunks.
- Pending records are excluded by default.
- Rejected records are always excluded.
- `--include-pending` creates a local preview only.
- PostgreSQL rejects any retrieval chunk whose review state is not `approved`.

Review decisions are stored in auditable batch files containing the reviewer, timestamp, record ID, decision and notes. `amu-apply-review` applies a batch without changing unrelated records.

## Chunk Contract

Each course becomes one complete chunk taken from the normalized course JSON:

```text
Course: Master of Computer Science and Applications (MCA)
Course Code: CAMSA
Faculty: Faculty of Science
Programme Level: postgraduate
Qualifying Examination: <reviewed eligibility text>
Age Limit: <reviewed age rule>
Selection Process: <reviewed selection rule>
Test Paper Details: <reviewed test information>
Course Details:
<all normalized table rows>
Source Pages: <printed and physical pages>
```

Retrieval searches this content directly. The retrieved chunk is passed to the answer-generating LLM with its source citation. Internal ranking scores and metadata are not included in the LLM context.

Chunk types:

| Type | Granularity | Parent use |
|---|---|---|
| `course_overview` | One complete chunk per course | Direct LLM context |
| `policy_section` | Existing heading-aware policy chunk | Source record only |
| `appendix_row` | One application, schedule or fee row | Source record only |

## PostgreSQL Layout

```text
documents
   ├── course_records
   │      └── retrieval_chunks.parent_course_id
   ├── policy_sections
   └── appendix_records

retrieval_chunks
   ├── generated tsvector + GIN index
   ├── pgvector embedding
   ├── source-page metadata
   └── approved-only constraint
```

The source tables retain complete JSON records for hydration and citations. The retrieval table stores compact searchable text.

## Ranking

`hybrid_search_chunks` independently ranks:

1. PostgreSQL full-text matches.
2. pgvector cosine matches.

It combines the rank positions using Reciprocal Rank Fusion with `k = 60`. Embeddings are dimension-agnostic until the embedding provider is selected. The MVP corpus is small enough for exact vector scans; add a dimension-specific HNSW index after the model is fixed.

## Query Flow

```text
Original query
  -> abbreviation expansion
  -> optional course/field filters
  -> full-text and vector candidate lists
  -> Reciprocal Rank Fusion
  -> selected complete information chunks
  -> LLM context containing chunk text and page citations
  -> grounded answer with page citations
```

## Commands

Build only approved chunks:

```powershell
$env:PYTHONPATH = "src"
python -m amu_admissions_rag.index_cli
```

Inspect all pending content without making it indexable:

```powershell
python -m amu_admissions_rag.index_cli --include-pending
```

Load reviewed records into PostgreSQL:

```bash
export AMU_RAG_DATABASE_URL="postgresql://..."
amu-load-index --apply-schema \
  --courses data/review/guide-2026-27.course-corpus.reviewed.json
```

`--apply-schema` runs the numbered migrations in `sql/` through the checksummed migration runner (`amu-migrate`). The loader performs an atomic replacement scoped to one document and refuses an empty approved corpus unless `--allow-empty` is explicitly supplied. It also stores each chunk's embedding, full source reference and load order, so the approved index can be rebuilt from the database exactly.

In normal operation the Docker `ingest` service runs all of these steps with `amu-pipeline`; see [DOCKER.md](DOCKER.md).

The project-owner full-guide review batch produces 1,723 approved chunks: 179 complete course chunks, 154 policy-section chunks and 1,390 appendix-row chunks. The earlier 15-course batch remains in the repository as the initial focused validation checkpoint.

## Deferred Decisions

- Embedding provider and dimensions
- Dimension-specific HNSW index
- Reranking provider
- Graph relationships, only if multi-hop evaluation demonstrates a real need
