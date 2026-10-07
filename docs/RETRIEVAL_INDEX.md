# Retrieval Index Design

## Scope

Phase 6 converts reviewed records into self-contained retrieval chunks and defines the PostgreSQL storage and hybrid-ranking layer. It does not add a graph database or choose an embedding provider.

## Approval Gate

- Approved records become index chunks.
- Pending records are excluded by default.
- Rejected records are always excluded.
- `--include-pending` creates a local preview only.
- PostgreSQL rejects any retrieval chunk whose review state is not `approved`.

## Chunk Contract

Every course child contains enough text to be found without first loading its parent:

```text
Course: Master of Computer Science and Applications (MCA)
Course Code: CAMSA
Faculty: Faculty of Science
Programme Level: postgraduate
Field: Qualifying Examination

<reviewed eligibility text>
```

It also stores the course record ID as `parent_record_id`. Retrieval searches the child text. Parent hydration uses the ID after a child has been selected.

Chunk types:

| Type | Granularity | Parent use |
|---|---|---|
| `course_overview` | One per course | Load complete course |
| `course_field` | One per named course field | Load course and sibling fields |
| `course_table_row` | One per normalized table row | Load complete table/course |
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
  -> selected child chunks
  -> parent course hydration where applicable
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

```powershell
$env:AMU_RAG_DATABASE_URL = "postgresql://..."
python -m amu_admissions_rag.load_index_cli --apply-schema
```

The loader performs an atomic replacement scoped to one document and refuses an empty approved corpus unless `--allow-empty` is explicitly supplied.

## Deferred Decisions

- Embedding provider and dimensions
- Dimension-specific HNSW index
- Reranking provider
- Graph relationships, only if multi-hop evaluation demonstrates a real need
