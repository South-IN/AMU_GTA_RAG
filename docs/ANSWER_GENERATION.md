# Grounded Answer Generation

Phase 9 connects approved retrieval chunks to Groq using `openai/gpt-oss-20b`.

The assistant is guide-wide and course-agnostic. MCA is used in examples only; there are no MCA-specific retrieval or generation rules. The 15 approved courses are the current human-validation checkpoint, not the product boundary. As the remaining reviewed course, policy and appendix records are approved, rebuilding the same index expands coverage without changing the answer pipeline.

## Flow

```text
User query
  -> approved complete-chunk retrieval
  -> content-and-citation context formatting
  -> Groq Chat Completions
  -> grounded answer with [SOURCE N] citations
```

The model receives only the user query and retrieved chunk content with printed-page citations. Coordinates, ranking scores and internal metadata are excluded.

## Grounding rules

- Answer only from supplied sources.
- Cite factual statements using `[SOURCE N]`.
- Do not invent requirements, dates, fees, intake values or pages.
- For eligibility, compare only facts explicitly stated by the applicant.
- State which required information is missing instead of declaring eligibility.
- Abstain when the retrieved guide evidence is insufficient.

## Configuration

Local secrets stay in the ignored `.env` file:

```text
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-20b
```

`.env.example` documents the required variables without containing credentials.

## Run

```powershell
$env:PYTHONPATH = "src"
& $python -m amu_admissions_rag.answer_cli `
  "I have completed 12 credits in Mathematics. Can I do MCA?" `
  --limit 1
```

Use `--discover-courses` for questions requesting several possible courses and `--json` for a structured response containing the answer, cited source list and retrieved chunk IDs.
