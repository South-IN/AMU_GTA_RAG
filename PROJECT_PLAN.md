# AMU Admissions Assistant

## Overview

Build a RAG assistant for the AMU Guide to Admissions 2026-27. The system will preserve course fields and tables, pass the extracted corpus through human validation, expand course abbreviations in user questions, retrieve relevant information, and answer with source-page citations.

## Core Objectives

- Answer questions about eligibility, fees, intake, dates, tests and admission rules
- Preserve relationships between field labels, values and nested tables
- Index only records and chunks approved through human validation
- Support variants such as `MCA`, `M.C.A.` and `M.CA`
- Cite the academic year and source page
- Refuse answers without supporting evidence

## Architecture

```text
Admissions PDF
1. Layout and table extraction
2. Course record and policy chunk creation
3. Human review and approval
4. PostgreSQL storage, full-text index and pgvector index
5. Abbreviation expansion and query classification
6. SQL lookup or hybrid retrieval
7. Grounded answer with citations
```

## PDF Ingestion

### Course records

Extract and preserve:

- Course name and code
- Faculty, programme level and campus
- Duration, specialization and intake
- Qualifying examination and age limit
- Selection process and test details
- Fees, application dates and test schedule
- Physical PDF page and printed page label

### Parsing tools

- PyMuPDF for text blocks and coordinates
- pdfplumber for nested tables
- Custom rules for label-value sections and merged cells

### Chunking

- One complete information chunk per course
- Policy chunks split at headings and numbered rules
- One structured record per appendix table row

Each course chunk contains its canonical identity, every narrative field, every normalized table row and all contributing source pages. Retrieved chunks are formatted as content plus citations and sent directly to the answer-generating LLM. Ranking scores and internal metadata are not included in that prompt.

### Human validation

- Review extracted fields against the original PDF page
- Correct table rows, merged values and page references
- Mark each record as pending, approved or rejected
- Store reviewer, review time and correction notes
- Index only approved records and chunks

The corpus starts fresh: every course, policy chunk and appendix row is pending until a reviewer approves it in a batch under `reviews/`. The 15 courses in [docs/HUMAN_VALIDATION_COURSES.md](docs/HUMAN_VALIDATION_COURSES.md) are the first review target.

## Query Processing

Preserve the original query and create an expanded copy for retrieval.

```text
Original: Am I eligible for M.CA?
Expanded: Am I eligible for Master of Computer Applications?
```

Processing steps:

1. Create a lowercase copy of the query
2. Run punctuation-tolerant course regex patterns
3. Replace matched abbreviations with full course names
4. Send the expanded query to retrieval
5. Keep the original query for display

The implementation preserves the original query exactly and modifies only recognized abbreviation spans. Intent rules supply soft field preferences for retrieval; they do not exclude other relevant chunks.

Example pattern:

```python
r"(?<!\w)m[\W_]*c[\W_]*a(?!\w)"
```

This matches `MCA`, `mca`, `M.C.A.`, `M.CA` and `M C A`.

## Retrieval Strategy

- Direct SQL lookup for fees, intake, dates, course codes and schedules
- PostgreSQL full-text search for exact terms and course names
- pgvector search for semantic questions
- Reciprocal Rank Fusion to combine text and vector results
- Intent-aware soft reranking before answer generation
- Parent-course hydration after child-chunk retrieval
- Local BM25 for exact-term retrieval; PostgreSQL full-text remains the deployment fallback

The local MVP runner uses BM25 now and a deterministic hashing-vector fallback so the complete workflow is testable without credentials. The embedding interface remains provider-neutral for a later hosted semantic model.

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python |
| PDF parsing | PyMuPDF and pdfplumber |
| Database | PostgreSQL or Supabase |
| Search | PostgreSQL full-text search and pgvector |
| API | FastAPI |
| Prototype UI | Streamlit |
| Deployment | Docker Compose: separate app, one-shot ingestion and PostgreSQL/pgvector containers |
| Generation | Hosted or local instruction model |

## 48-Hour Implementation Plan

| Time | Work | Output |
|---|---|---|
| 0-4 hours | Define schema and test questions | Data model and evaluation set |
| 4-14 hours | Extract course fields and tables | Normalized course records |
| 10-18 hours | Review extracted records | Approved corpus |
| 14-22 hours | Build database and indexes | Searchable knowledge base |
| 20-30 hours | Add abbreviation expansion and retrieval | Query API |
| 26-36 hours | Build the chat interface | End-to-end prototype |
| 36-44 hours | Test and correct failures | Evaluation results |
| 44-48 hours | Prepare demo and presentation | Final submission |

## Evaluation

Test:

- Course eligibility
- Intake and fee lookup
- Application and test dates
- Course comparison
- General admission rules
- Abbreviation variants
- Ambiguous and unsupported questions

MVP targets:

- At least 95% accuracy for exact facts
- Every factual answer cites a source or abstains
- Median response time below five seconds
- Correct course match across abbreviation variants
- All indexed records have human approval

## Risks and Controls

| Risk | Control |
|---|---|
| Merged table cells lose context | Forward-fill shared values and validate rows |
| Extraction errors enter retrieval | Require human approval before indexing |
| Similar course names retrieve the wrong record | Filter by course code, faculty, level and campus |
| Abbreviation collision | Ask for clarification when multiple courses match |
| Unsupported answer | Require retrieved evidence before generation |
| Guide changes | Version documents by academic year and checksum |

## Definition of Done

- Course fields and nested tables remain connected
- Human reviewers approve the indexed corpus
- Course abbreviations expand correctly
- Exact facts use validated records
- Policy answers use retrieved passages
- Answers include source pages
- Unsupported questions receive a clear refusal
- The demo covers at least five question types

---

# PPT Overview

The six-slide presentation should explain the problem, solution, technical approach, feasibility, impact and supporting evidence. Use screenshots and diagrams instead of long paragraphs.

## Slide 1: Title

**Title:** AMU Admissions Assistant

- Subtitle: Verified answers from the official admissions guide
- Team name and members
- Institution and hackathon
- Visual of the guide beside a sample user question

## Slide 2: Proposed Solution

- Applicants must search a long guide with repeated course sections and nested tables
- Important facts appear across course pages and appendices
- The assistant answers natural-language questions with citations
- Exact facts use structured records
- Rules and explanations use RAG
- Course abbreviations expand before retrieval
- The searchable corpus contains human-validated records

Visual: a PDF page beside a cited answer.

## Slide 3: Technical Approach

- PDF layout and table extraction
- Structured course records and policy chunks
- Human validation before indexing
- PostgreSQL full-text search and pgvector
- Abbreviation replacement
- SQL lookup or hybrid retrieval
- Grounded answer generation with citations

Visual: an editable architecture flow and a small extracted course example.

## Slide 4: Feasibility and Viability

- The PDF contains selectable text and recurring layouts
- Human review verifies extracted fields before publication
- The MVP does not require custom model training
- Main risks and controls
- Short implementation timeline
- Support for future guides and supplements

Visual: implementation timeline with a compact risk table.

## Slide 5: Impact and Benefits

- Faster access to course information
- Easier comparison of eligibility, fees and schedules
- Fewer repetitive help-desk questions
- Consistent answers with source pages
- Higher trust through a human-reviewed corpus
- MVP accuracy, citation and response-time targets

Visual: target users connected to measurable outcomes.

## Slide 6: Research and References

- AMU Guide to Admissions 2026-27
- Course-page screenshot and extracted record
- Human-validation workflow and approval evidence
- Prototype answer with citation
- Evaluation questions and results
- Repository and live-demo QR codes
- Technical documentation references
- Disclaimer that official notices and amendments take precedence

Visual: original PDF section, extracted data and prototype result.
