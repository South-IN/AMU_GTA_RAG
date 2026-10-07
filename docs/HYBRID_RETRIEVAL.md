# Hybrid Retrieval

Phase 8 provides a runnable retrieval path over the approved corpus.

## Request flow

1. Preserve the original question and expand recognized course abbreviations.
2. Detect intent and produce soft field preferences.
3. Search the same self-contained chunks with BM25 and vector similarity.
4. Fuse both ranked lists with Reciprocal Rank Fusion (RRF).
5. Add small soft boosts for a requested field and exact structured values such as branch names or course codes.
6. Return source-page provenance and hydrate linked course parents.

Parent hydration happens after retrieval. It gives the application the complete reviewed course record and sibling fields while the retrieved child remains the cited evidence.

## Multi-granularity course discovery

Every approved course has two retrieval representations:

- A content-rich course profile containing all narrative fields and a bounded table summary. It is used to discover and rank complete courses.
- Focused field and table-row chunks. They provide precise evidence and page citations.

Course discovery ranks only course profiles, applies a soft programme-progression preference when the applicant explicitly reports a completed qualification, hydrates the complete parent record, and then attaches the most relevant child evidence. Table summaries include at most 20 rows; the hydrated parent and table-row chunks retain every row.

This is relational parent aggregation, not graph retrieval. A course profile is a recall document and must not be used as the sole citation when its content spans pages.

## Embedding boundary

`EmbeddingProvider` is provider-neutral. Phase 8 includes `HashingEmbeddingProvider`, a deterministic NumPy-only word/bigram/character feature vectorizer, so the entire pipeline can be run offline without credentials.

The hashing provider validates vector storage, cosine ranking, fusion and parent hydration. It is not a learned semantic model and is not the production quality benchmark. A hosted embedding API can replace it by implementing `embed_texts`; no BM25, RRF or response-model code needs to change.

## Commands

```powershell
$env:PYTHONPATH = "src"
& $python -m amu_admissions_rag.retrieval_cli "Am I eligible for M.C.A.?" --limit 5
& $python -m amu_admissions_rag.retrieval_cli `
  "I completed B.Sc. Computer Science. Which courses am I eligible for?" `
  --discover-courses --limit 5
& $python -m amu_admissions_rag.evaluate_retrieval_cli `
  --limit 5 `
  --output data/processed/phase8-retrieval-evaluation.json
& $python -m amu_admissions_rag.evaluate_retrieval_cli `
  --discover-courses `
  --queries evaluation/course_discovery_queries.json `
  --limit 3 `
  --output data/processed/phase8-course-discovery-evaluation.json
```

The checked-in evaluation questions cover all 15 approved sample courses. Generated reports stay outside Git with the other processed artifacts.

## MVP decisions

- BM25 is used locally because it handles exact course names, codes and admission terminology well.
- Vector similarity remains active in every query, even with the offline fallback.
- RRF avoids trying to compare incomparable raw lexical and vector scores.
- Intent is a soft reranking signal, never a filter.
- Only approval-gated chunks are searched.
- Results retain physical and printed pages for citations.
- The PostgreSQL/pgvector path remains the deployment target; this local backend makes tests and demos independent of database credentials.
