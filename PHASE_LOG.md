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
