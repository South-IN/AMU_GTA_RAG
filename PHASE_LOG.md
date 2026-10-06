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
