# Query Processing

## Contract

The system preserves the original question and creates a separate retrieval query. It does not lowercase, remove punctuation from or collapse whitespace across the whole question.

```text
Original: Am I eligible for M.CA?
Expanded: Am I eligible for Master of Computer Science and Applications?
```

Only recognized course abbreviations are replaced. Each abbreviation uses a case-insensitive regex that permits spaces, periods, underscores and hyphens between letters while enforcing word boundaries.

For `MCA`, the effective pattern is equivalent to:

```python
r"(?<!\w)m[\s._-]*c[\s._-]*a(?!\w)"
```

It matches `MCA`, `mca`, `M.C.A.`, `M.CA` and `M C A` without matching the letters inside another word.

### Guide spellings and word-like aliases

Aliases can list extra spellings made of multi-letter segments, so the guide's own forms expand too: `B.Lib.I.Sc.`, `M.Lib.I.Sc.`, `M. Arch.`, `M. Plan.`, `P.G. Diploma` and `PGDCP`. `B.P.Ed.`, `M.P.Ed.` and `BPT` are also covered.

Some aliases spell ordinary words: `BED`, `MED`, `MA`, `BA`, `BE` and `MARCH`. These match only:

- in capitals (`BED`, `MA`);
- in the segment case of their spelling (`BEd`, `MArch`, `B Ed`);
- with a period after the first segment, in any case (`b.ed`, `m.a.`, `M. Arch.`).

So "hostel bed", "study med", "ma'am" and "exams in March" are left unchanged.

### Coverage check

`unrecognised_abbreviations()` reports abbreviation-like spans in a course name that no alias covers. A test runs it over every course name parsed from the 2026-27 guide (`tests/fixtures/guide-2026-27-course-names.json`), and `amu-pipeline` logs a warning when a newly ingested guide introduces an abbreviation without an alias. Subject acronyms that are not course abbreviations, such as `GIS`, are listed in `NON_COURSE_ACRONYMS`.

## Intent Hints

Lightweight rules attach retrieval preferences:

| Query wording | Intent | Preferred field |
|---|---|---|
| eligible, qualification | eligibility | `qualifying_examination` |
| age, older, younger | age limit | `age_limit` |
| selection, admission process | selection | `selection_process` |
| exam pattern, syllabus | test details | `test_paper_details` |
| test centre/location | test centres | `test_centres` |
| seats, intake | intake | `course_details` |
| duration, semesters | duration | `course_details` |
| fee, cost | fees | `fee_summary` |
| application deadline | application dates | `application_summary` |
| exam date/time | test schedule | `test_schedule` |

These are ranking hints, not hard filters. Hybrid retrieval may still return other fields when they are relevant.

## Index Alignment

Self-contained course chunks repeat a full-name expansion when the PDF course title is abbreviation-only. For example:

```text
Course: M.B.B.S.
Expanded Course Name: Bachelor of Medicine and Bachelor of Surgery
```

This ensures that the expanded user query and indexed text share the same vocabulary.

## CLI

The default output is only the expanded question:

```powershell
python -m amu_admissions_rag.query_cli "Am I eligible for M.C.A.?"
```

Internal routing details are available for development:

```powershell
python -m amu_admissions_rag.query_cli "Am I eligible for M.C.A.?" --debug
```
