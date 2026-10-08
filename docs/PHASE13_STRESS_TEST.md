# Phase 13 complex-query stress test

Date: 2026-10-08

This was a live end-to-end check of retrieval, policy-context merging, Groq
generation and citation handling against the full approved guide corpus. The
provider rate limit stopped the fifth case, so only completed cases are scored.

| Case | Query focus | Result | Observation |
|---|---|---|---|
| C1 | M.Tech. CSE eligibility, specialization and intake | Partial | Correct course evidence ranked first, but the answer interpreted the shared intake of 20 as 20 seats per specialization. |
| C2 | B.A. (Hons.) routes and requirements | Partial | The three relevant B.A. course records were retrieved, but the answer added an unsupported statement that every faculty entry continues on the next page. |
| C3 | B.Sc. (Hons.) Community Science eligibility and registration | Pass | Retrieved the complete course record and the relevant CUET policy; the answer correctly supplied the missing registration details with citations. |
| C4 | BUMS eligibility, age and selection | Mostly pass | Retrieved BUMS and relevant maximum-age policy and answered cautiously; Pre-Tib and an unrelated sports policy were extra context. |
| C5 | MBA multi-part query | Not scored | The Groq rate limit was reached before an answer completed. |

## Findings

- Policy-aware retrieval works across courses beyond the original validation sample.
- Source markers remained connected to retrieved page evidence in completed answers.
- Remaining refinement targets are table-semantics grounding, unsupported inference
  detection and tighter policy filtering.
- No ranking or prompt changes were made from this test alone; the results are a
  reproducible refinement baseline.
