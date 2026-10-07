CREATE EXTENSION IF NOT EXISTS vector;

DO $$
BEGIN
    CREATE TYPE review_status AS ENUM ('pending', 'approved', 'rejected');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE retrieval_chunk_type AS ENUM (
        'course_overview',
        'course_field',
        'course_table_row',
        'policy_section',
        'appendix_row'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    total_pages INTEGER NOT NULL CHECK (total_pages > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS course_records (
    record_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    course_name TEXT NOT NULL,
    course_code TEXT,
    faculty TEXT NOT NULL,
    program_level TEXT NOT NULL,
    campus TEXT,
    physical_page INTEGER NOT NULL CHECK (physical_page > 0),
    printed_page TEXT,
    content JSONB NOT NULL,
    review_status review_status NOT NULL,
    reviewer TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    CHECK (
        review_status = 'pending'
        OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS policy_sections (
    record_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    heading TEXT NOT NULL,
    physical_page INTEGER NOT NULL CHECK (physical_page > 0),
    printed_page TEXT,
    content JSONB NOT NULL,
    review_status review_status NOT NULL,
    reviewer TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    CHECK (
        review_status = 'pending'
        OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS appendix_records (
    record_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    appendix_type TEXT NOT NULL,
    course_name TEXT NOT NULL,
    course_code TEXT,
    physical_page INTEGER NOT NULL CHECK (physical_page > 0),
    printed_page TEXT,
    content JSONB NOT NULL,
    review_status review_status NOT NULL,
    reviewer TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    CHECK (
        review_status = 'pending'
        OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS retrieval_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    chunk_type retrieval_chunk_type NOT NULL,
    source_record_id TEXT NOT NULL,
    parent_course_id TEXT REFERENCES course_records(record_id) ON DELETE CASCADE,
    field_name TEXT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    physical_page INTEGER NOT NULL CHECK (physical_page > 0),
    printed_page TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_status review_status NOT NULL CHECK (review_status = 'approved'),
    embedding_model TEXT,
    embedding vector,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A')
        || setweight(to_tsvector('english', coalesce(content, '')), 'B')
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (
            chunk_type IN ('course_overview', 'course_field', 'course_table_row')
            AND parent_course_id IS NOT NULL
        )
        OR (
            chunk_type IN ('policy_section', 'appendix_row')
            AND parent_course_id IS NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS retrieval_chunks_fts_idx
    ON retrieval_chunks USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS retrieval_chunks_parent_course_idx
    ON retrieval_chunks (parent_course_id);
CREATE INDEX IF NOT EXISTS retrieval_chunks_field_idx
    ON retrieval_chunks (field_name);
CREATE INDEX IF NOT EXISTS retrieval_chunks_course_code_idx
    ON retrieval_chunks ((metadata ->> 'course_code'));
CREATE INDEX IF NOT EXISTS retrieval_chunks_appendix_type_idx
    ON retrieval_chunks ((metadata ->> 'appendix_type'));

-- Embeddings remain dimension-agnostic until the provider is finalized. At MVP
-- scale, pgvector performs an exact cosine scan. Add a dimension-specific HNSW
-- index after the embedding model and dimensions are locked.

CREATE OR REPLACE FUNCTION hybrid_search_chunks(
    query_text TEXT,
    query_embedding vector,
    result_limit INTEGER DEFAULT 10,
    candidate_limit INTEGER DEFAULT 50,
    rrf_k INTEGER DEFAULT 60
)
RETURNS TABLE (
    chunk_id TEXT,
    parent_course_id TEXT,
    chunk_type retrieval_chunk_type,
    title TEXT,
    content TEXT,
    physical_page INTEGER,
    printed_page TEXT,
    metadata JSONB,
    score DOUBLE PRECISION
)
LANGUAGE SQL
STABLE
AS $$
WITH text_candidates AS (
    SELECT
        candidate.chunk_id,
        row_number() OVER (
            ORDER BY ts_rank_cd(
                candidate.search_vector,
                websearch_to_tsquery('english', query_text)
            ) DESC
        ) AS rank_position
    FROM retrieval_chunks AS candidate
    WHERE candidate.search_vector @@ websearch_to_tsquery('english', query_text)
    ORDER BY ts_rank_cd(
        candidate.search_vector,
        websearch_to_tsquery('english', query_text)
    ) DESC
    LIMIT candidate_limit
),
vector_candidates AS (
    SELECT
        candidate.chunk_id,
        row_number() OVER (
            ORDER BY candidate.embedding <=> query_embedding
        ) AS rank_position
    FROM retrieval_chunks AS candidate
    WHERE query_embedding IS NOT NULL
      AND candidate.embedding IS NOT NULL
    ORDER BY candidate.embedding <=> query_embedding
    LIMIT candidate_limit
),
fused AS (
    SELECT
        coalesce(text_candidates.chunk_id, vector_candidates.chunk_id) AS chunk_id,
        coalesce(
            1.0 / (rrf_k + text_candidates.rank_position),
            0.0
        ) + coalesce(
            1.0 / (rrf_k + vector_candidates.rank_position),
            0.0
        ) AS score
    FROM text_candidates
    FULL OUTER JOIN vector_candidates USING (chunk_id)
)
SELECT
    chunk.chunk_id,
    chunk.parent_course_id,
    chunk.chunk_type,
    chunk.title,
    chunk.content,
    chunk.physical_page,
    chunk.printed_page,
    chunk.metadata,
    fused.score
FROM fused
JOIN retrieval_chunks AS chunk USING (chunk_id)
ORDER BY fused.score DESC, chunk.chunk_id
LIMIT result_limit;
$$;
