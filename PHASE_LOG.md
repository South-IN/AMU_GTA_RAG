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
