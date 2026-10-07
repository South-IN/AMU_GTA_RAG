-- Store enough chunk provenance to rebuild the exact approved index from the
-- database, keep corpus order stable for deterministic ranking, and record
-- every ingestion run for auditing and change detection.

ALTER TABLE course_records
    ADD COLUMN IF NOT EXISTS load_position INTEGER;

ALTER TABLE retrieval_chunks
    ADD COLUMN IF NOT EXISTS load_position INTEGER,
    ADD COLUMN IF NOT EXISTS source JSONB;

CREATE INDEX IF NOT EXISTS retrieval_chunks_document_position_idx
    ON retrieval_chunks (document_id, load_position);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id BIGSERIAL PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
    pipeline_version TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    review_batches JSONB NOT NULL DEFAULT '[]'::jsonb,
    course_records INTEGER NOT NULL CHECK (course_records >= 0),
    policy_sections INTEGER NOT NULL CHECK (policy_sections >= 0),
    appendix_records INTEGER NOT NULL CHECK (appendix_records >= 0),
    retrieval_chunks INTEGER NOT NULL CHECK (retrieval_chunks >= 0),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ingestion_runs_document_loaded_idx
    ON ingestion_runs (document_id, loaded_at DESC);
