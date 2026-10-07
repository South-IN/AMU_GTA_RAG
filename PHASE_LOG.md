# Phase Log

## Phase 1: Project Foundation

**Status:** Complete
**Date:** 2026-10-06

### Changes

- Initialized the Git repository on the `main` branch
- Added the Python package, configuration and test structure
- Added dependency and lint configuration in `pyproject.toml`
- Added repository documentation and ignore rules
- Preserved the supplied admissions guide as the source corpus

### Decisions

- Use a `src` package layout
- Use built-in `unittest` so baseline tests run without installing development packages
- Keep generated extraction and review outputs outside Git by default

### Validation

- Configuration tests verify project-root and source-PDF discovery

## Phase 2: Data Models

**Status:** Complete
**Date:** 2026-10-06

### Changes

- Added validated models for documents, course records, sections, tables and source references
- Added review states with reviewer and timestamp requirements for completed reviews
- Added the 15-course human-validation sample across programme levels and faculties
- Added the page-indexed list of required guide sections

### Decisions

- Every extracted item retains physical-page and printed-page provenance
- Human review uses pending, approved and rejected states
- Only approved records will be eligible for indexing
- The validation sample includes merged tables, shared degree tables and narrative layouts

### Validation

- Model tests cover provenance, review-state requirements and invalid coordinates

## Phase 3: PDF Extraction

**Status:** Complete
**Date:** 2026-10-06

### Changes

- Added PDF metadata and SHA-256 fingerprint extraction
- Added positioned text-line extraction with bounding boxes and font metadata
- Added printed-page-label detection
- Added table extraction with bounding boxes and normalized cell text
- Added a CLI for extracting selected physical pages to JSON

### Decisions

- Use pdfplumber for positioned text and tables
- Use pypdf for document metadata and page count
- Keep raw extraction separate from later course normalization
- Select physical pages explicitly so extraction can run incrementally

### Validation

- Smoke tests cover the PDF cover, an undergraduate course page and a landscape appendix
- Tests verify the 187-page count, document fingerprint, page labels and detected tables
- CLI smoke extraction produced valid JSON for physical pages 54 and 128

## Phase 4: Course Structure Parsing

**Status:** Complete
**Date:** 2026-10-06

### Changes

- Added course-card segmentation from repeated Course of Study anchors
- Added normalized field extraction for eligibility, age, selection and test information
- Added course-detail table normalization for branches, specializations and campuses
- Added forward-fill handling for visually merged duration and intake cells
- Added programme-level, faculty-context and source-page assignment
- Added a CLI that writes pending course records for human validation
- Rejected narrative uses of "Course of Study" when they produce neither course fields nor a normalized course table
- Added a metadata-light JSON export for human reviewers that preserves content, tables, review state and page references
- Added bounded cross-page continuation parsing for course cards that spill onto the next physical page
- Normalized split visual labels such as Qualifying/Examination and Additional/Information
- Corrected Test Centre(s) field recognition so it is not absorbed into test-paper details

### Decisions

- Keep parent courses with multiple branches or specializations as one record with table rows
- Preserve inherited table values and mark them as inherited
- Leave every parsed record in pending review state
- Carry faculty context across sequential pages and allow an explicit starting faculty

### Validation

- Tests cover standard course cards, multiple courses on one page and specialization tables
- Tests verify course codes, fields, faculty context and merged-cell inheritance
- Undergraduate smoke parsing produced 31 pending records with no unresolved faculty values
- All 31 undergraduate records retained at least one normalized course-detail table
- Full-guide extraction processed all 187 physical pages into 8,642 positioned lines and 697 raw tables
- Full-guide parsing produced 179 pending course records across 66 course pages
- The final pending corpus contains 180 normalized course tables, 372 table rows and no unresolved faculties or duplicate record IDs
- Regression coverage rejects three narrative false positives found during the first full-document run
- Reviewer-export tests verify that technical IDs, hashes and bounding boxes are removed without losing reviewable values
- Cross-page regression tests recover the Community Science third note and the B.A. (Hons.) English eligibility continuation
- Boundary tests prevent new sections and non-consecutive page selections from being merged into preceding courses
- Full-corpus comparison retained all 179 record IDs, 180 tables and 372 table rows with no non-field changes

## Phase 5: Policy and Appendix Corpus

**Status:** Complete
**Date:** 2026-10-07

### Changes

- Added heading-aware policy chunking for required non-course pages
- Added normalized records for the application summary, test schedule and fee summary appendices
- Added forward-fill tracking for visually merged application and schedule cells
- Added multi-paper test-schedule continuation handling
- Added programme-group, faculty, physical-page and printed-page provenance
- Added a CLI that builds the complete pending policy corpus from the full extraction
- Normalized split initial-letter artifacts in appendix course names
- Distinguished external application methods such as NEET from processing charges

### Decisions

- Keep every policy chunk within one physical page so citations remain exact
- Cap policy chunks at 300 words and split first at detected headings
- Store each appendix course row as an independently reviewable record
- Mark forward-filled appendix values as inherited and retain the originating source page
- Keep all newly generated policy and appendix records pending human review
- Treat the reported course verification as a completed project checkpoint without inventing reviewer identity or approval timestamps in the corpus

### Validation

- The full run produced 154 policy chunks across every required narrative/form page
- The appendices produced 480 application rows, 328 test-schedule rows and 582 fee rows
- All 1,544 generated record IDs are unique and all records remain in pending state
- No generated appendix record has an empty value set or missing programme-group context
- Repeated guide headers do not appear in policy chunk text
- Regression tests cover merged application values, NEET application methods, deferred dates, multi-paper schedules, inherited schedules, fees and extraction spacing artifacts
- The complete test suite passes 32 tests

## Phase 6: Retrieval Chunks and PostgreSQL Index Foundation

**Status:** Complete
**Date:** 2026-10-07

### Changes

- Added self-contained course overview, field and table-row chunk generation
- Added `parent_record_id` links for relational course hydration
- Added independently searchable policy-section and appendix-row chunks
- Added approval-gated index generation with a separate pending preview mode
- Added PostgreSQL tables for documents, source records and retrieval chunks
- Added generated full-text vectors, GIN indexes and pgvector storage
- Added Reciprocal Rank Fusion for combined full-text and vector ranking
- Added an atomic PostgreSQL loader scoped to one guide document
- Added auditable review batches and a CLI for applying reviewer decisions
- Added retrieval-index architecture and operating documentation

### Decisions

- Repeat canonical course context inside every child chunk so retrieval does not depend on loading the parent first
- Use the parent relationship only after retrieval for course hydration and sibling-field access
- Keep policy chunks and appendix rows independent rather than forcing artificial course relationships
- Permit only approved records in the database retrieval table
- Keep pgvector dimension-agnostic until the embedding provider is finalized
- Use exact vector scans for the MVP-sized corpus and defer HNSW until dimensions are fixed
- Defer graph retrieval until multi-hop evaluation demonstrates measurable benefit

### Validation

- The full pending preview contains 2,960 unique chunks
- Preview composition is 179 course overviews, 865 course fields, 372 course table rows, 154 policy sections and 1,390 appendix rows
- All 1,416 course chunks contain course context and a parent record ID
- Recorded the project owner's 15-course validation sample with reviewer, timestamp and notes
- The approved-only build contains 190 chunks across 15 reviewed course records
- Policy and appendix records remain pending and are excluded from the approved index
- The empty-corpus guard prevents accidental deletion of an existing database index
- Tests cover self-contained content, persisted parent links, approval gating, PostgreSQL constraints and RRF structure
- The complete test suite passes 47 tests
- Live PostgreSQL loading was not run because the available local server requires unavailable credentials and does not have pgvector installed

## Phase 7: Query Normalization and Intent Routing

**Status:** Complete
**Date:** 2026-10-07

### Changes

- Added punctuation-tolerant course-abbreviation expansion
- Preserved the original query and all non-alias casing, punctuation and whitespace
- Added lightweight multi-intent detection with retrieval field preferences
- Added full-name enrichment for abbreviation-only course titles in retrieval chunks
- Added a CLI with plain expanded output and optional debug metadata
- Added query-processing documentation and examples

### Decisions

- Modify only recognized abbreviation spans instead of normalizing the entire query
- Use boundary-aware patterns to prevent aliases from matching inside ordinary words
- Keep intent detection deterministic and inexpensive for the MVP
- Treat intent fields as ranking hints rather than hard retrieval filters
- Keep the original query for display and use the expanded query only for retrieval

### Validation

- `MCA`, `mca`, `M.C.A.`, `M.CA` and `M C A` produce the same expansion
- Multiple aliases in one question expand independently
- Abbreviation punctuation is removed without consuming surrounding sentence punctuation
- Unrelated capitalization, spacing and punctuation remain unchanged
- Eligibility and multi-intent questions select the expected preferred fields
- Evaluation follow-up recognizes `apply for` and subject requirements as eligibility, and `how long` as duration
- The reviewed sample still builds 190 approved retrieval chunks after name enrichment
- The complete test suite passes 59 tests

## Phase 8: Hybrid Retrieval and Parent Hydration

**Status:** Complete
**Date:** 2026-10-07

### Changes

- Added a dependency-free BM25 implementation for local lexical retrieval
- Added a provider-neutral embedding interface and deterministic NumPy hashing-vector fallback
- Added cosine vector ranking and Reciprocal Rank Fusion across both retrieval paths
- Added intent-aware soft reranking without filtering alternative evidence
- Added parent-course hydration for retrieved child chunks
- Added human-readable and JSON retrieval CLI output with page provenance
- Added a 16-query evaluation set spanning all 15 approved sample courses
- Added an evaluation runner that records top-k hits and pass/fail evidence

### Decisions

- Always execute both lexical and vector retrieval for the MVP
- Use RRF because lexical and vector raw scores are not directly comparable
- Keep intent preferences as boosts so imperfect classification cannot hide evidence
- Use the local hashing embedder only for offline pipeline validation, not as a claim of learned semantic quality
- Keep the embedding provider swappable for a hosted model during refinement
- Hydrate parents only after ranking; child chunks remain self-contained and citable
- Search only the 190 chunks derived from the 15 approved course records

### Validation

- The complete test suite passes 65 tests
- Deterministic vector generation, BM25/RRF ranking, field boosts and parent hydration have regression coverage
- Exact structured-value matching resolves close branch and specialization ranking ties
- The approved corpus rebuild still contains 190 chunks
- The varied retrieval evaluation passes 16/16 cases at top-5
- The evaluation covers eligibility, age, selection, tests, test centres and intake/table-row queries
- Every evaluated course in the human-validated sample is represented
