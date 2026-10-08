# Streamlit Admissions Assistant

Phase 10 adds a chat interface over the existing retrieval and generation pipeline.

## Run locally

Create `.env` from `.env.example`, set `GROQ_API_KEY`, then run:

```powershell
$env:PYTHONPATH = "src"
python -m streamlit run streamlit_app.py
```

## Interface behavior

- Suggested questions help first-time users understand the supported scope.
- Chat history stays in the Streamlit session.
- Direct questions use hybrid retrieval; course-suggestion questions automatically use course discovery.
- Recognized abbreviations are expanded before retrieval.
- Answers use clickable numeric citations that jump to their source cards.
- Source cards show the course or section title, printed guide page, a preview and the complete retrieved context.
- The official guide can be downloaded from the sidebar.
- The sidebar states the active full-guide coverage: 179 courses, 154 policy sections and 1,390 appendix rows.

## Citation and eligibility safety

Only valid `[SOURCE N]` markers are converted to links. Missing or invalid markers trigger one constrained citation-repair pass. Retrieved chunks that the answer does not cite are labelled **Retrieved evidence**, not **Cited source**.

Course-discovery answers receive an additional deterministic check for overconfident eligibility language. When triggered, a constrained safety pass rewrites the answer to:

- describe courses as potential matches;
- use only applicant facts stated in the question;
- separate satisfied requirements from missing marks, credits, subjects, age or other prerequisites;
- retain source citations.

The assistant service is independent of Streamlit and remains reusable from the CLI or a future API.
