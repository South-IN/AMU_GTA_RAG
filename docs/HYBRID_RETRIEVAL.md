# Hybrid Retrieval

Phase 8 provides a runnable retrieval path over the approved corpus.

## Request flow

1. Preserve the original question and expand recognized course abbreviations.
2. Detect intent and produce soft field preferences.
3. Search the same self-contained chunks with BM25 and vector similarity.
4. Fuse both ranked lists with Reciprocal Rank Fusion (RRF).
5. Return the highest-ranked complete information chunks.
6. Format only their content and page citations for the answer-generating LLM.

Ranking scores and internal metadata are not sent to the LLM.

## Chunk contract

The current design deliberately uses one retrieval representation per record:

- One complete chunk per course, including every narrative field and every normalized table row.
- One chunk per policy section.
- One chunk per appendix row.

Course chunks list every contributing printed and physical page. Retrieval can return several complete courses for comparison. The LLM receives the retrieved information directly and is instructed to answer only from those sources.

## Embedding boundary

`EmbeddingProvider` is provider-neutral. Phase 8 includes `HashingEmbeddingProvider`, a deterministic NumPy-only word/bigram/character feature vectorizer, so the entire pipeline can be run offline without credentials.

The hashing provider validates vector storage, cosine ranking, fusion and parent hydration. It is not a learned semantic model and is not the production quality benchmark. A hosted embedding API can replace it by implementing `embed_texts`; no BM25, RRF or response-model code needs to change.

## Policy-aware context assembly

Answer generation performs two retrieval passes over the same approved index:

1. Primary hybrid retrieval selects course, appendix or policy evidence for the question.
2. A filtered hybrid pass selects up to two additional `policy_section` chunks using the same expanded query.

The results are merged in primary-first order and deduplicated before citation numbering. This uses the existing policy chunks and embeddings; it does not require rechunking or reindexing.

## Commands

```powershell
$env:PYTHONPATH = "src"
& $python -m amu_admissions_rag.retrieval_cli "Am I eligible for M.C.A.?" --limit 5
& $python -m amu_admissions_rag.retrieval_cli `
  "I have 12 Mathematics credits. Can I do MCA?" `
  --limit 1 --llm-context
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

The checked-in evaluation questions cover all 15 approved sample courses. Generated reports store each query, its expanded form, the complete retrieved chunk text, rank, score and source pages. Reports stay outside Git with the other processed artifacts.

## MVP decisions

- BM25 is used locally because it handles exact course names, codes and admission terminology well.
- Vector similarity remains active in every query, even with the offline fallback.
- RRF avoids trying to compare incomparable raw lexical and vector scores.
- Intent is a soft reranking signal, never a filter.
- Only approval-gated chunks are searched.
- Results retain physical and printed pages for citations.
- The PostgreSQL/pgvector path remains the deployment target; this local backend makes tests and demos independent of database credentials.
