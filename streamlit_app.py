"""Streamlit interface for the AMU Admissions Guide assistant."""

from __future__ import annotations

import html
import sys
from collections import Counter
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from amu_admissions_rag.assistant import AdmissionsAssistant, AssistantReply
from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.corpus import load_approved_corpora
from amu_admissions_rag.presentation import context_preview, link_answer_citations


st.set_page_config(
    page_title="AMU Admissions Guide",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --amu-green: #0b5d3b;
        --amu-deep: #073d2a;
        --amu-mint: #eaf6f0;
        --amu-gold: #d9a928;
        --ink: #17231d;
    }
    .stApp { background: linear-gradient(180deg, #f7fbf8 0%, #ffffff 34%); }
    .block-container { max-width: 1040px; padding-top: 2.1rem; }
    .hero {
        padding: 1.55rem 1.7rem;
        border: 1px solid rgba(11, 93, 59, .16);
        border-radius: 22px;
        background: linear-gradient(125deg, #073d2a 0%, #0b5d3b 66%, #167a52 100%);
        box-shadow: 0 18px 45px rgba(7, 61, 42, .16);
        color: white;
        margin-bottom: 1.3rem;
    }
    .hero-kicker { color: #f2cf6b; font-size: .78rem; font-weight: 800; letter-spacing: .14em; }
    .hero h1 { color: white; font-size: 2.15rem; margin: .35rem 0 .4rem; letter-spacing: -.03em; }
    .hero p { color: #dcece4; margin: 0; max-width: 760px; font-size: 1.02rem; }
    .trust-row { display: flex; gap: .55rem; flex-wrap: wrap; margin-top: 1rem; }
    .trust-pill {
        background: rgba(255,255,255,.11); border: 1px solid rgba(255,255,255,.17);
        padding: .34rem .68rem; border-radius: 999px; color: #f4faf6; font-size: .78rem;
    }
    [data-testid="stChatMessage"] {
        border: 1px solid rgba(11, 93, 59, .10);
        border-radius: 18px;
        padding: .35rem .55rem;
        background: rgba(255,255,255,.86);
    }
    [data-testid="stChatMessage"] a { color: var(--amu-green); font-weight: 800; }
    [data-testid="stSidebar"] { background: #f1f7f3; border-right: 1px solid #dfeae3; }
    .source-label { color: var(--amu-green); font-weight: 800; font-size: .78rem; letter-spacing: .05em; }
    .source-preview { color: #44554b; font-size: .91rem; line-height: 1.55; }
    .coverage-note {
        padding: .75rem .85rem; border-radius: 12px; background: #fff8df;
        border: 1px solid #f0dda0; color: #5f4b13; font-size: .84rem;
    }
    .stButton > button { border-radius: 12px; border-color: #c8ddd0; }
    .stButton > button:hover { border-color: var(--amu-green); color: var(--amu-green); }
    </style>
    """,
    unsafe_allow_html=True,
)


EXAMPLE_QUESTIONS = (
    "I have 12 Mathematics credits. Can I apply for M.C.A.?",
    "How are candidates selected for M.B.A.?",
    "What are the eligibility and selection requirements for M.B.B.S.?",
    "I completed B.Sc. Computer Science. Which postgraduate courses may fit?",
)


@st.cache_resource(show_spinner=False)
def load_assistant() -> AdmissionsAssistant:
    return AdmissionsAssistant.from_project()


@st.cache_data(ttl=60, show_spinner=False)
def approved_coverage() -> dict[str, int] | None:
    try:
        index, _ = load_approved_corpora()
    except Exception:
        return None
    counts = Counter(chunk.chunk_type.value for chunk in index.chunks)
    return {
        "courses": counts["course_overview"],
        "policy": counts["policy_section"],
        "appendix": counts["appendix_row"],
    }


def coverage_text(coverage: dict[str, int] | None) -> str:
    if coverage is None:
        return "Approved coverage could not be loaded."
    if not any(coverage.values()):
        return (
            "No guide records have been approved yet. Answers become available as "
            "reviewers approve content."
        )
    return (
        f"{coverage['courses']} courses, {coverage['policy']} policy sections and "
        f"{coverage['appendix']} appendix rows are approved and searchable. "
        "Coverage grows as more records are approved."
    )


def render_sources(reply: AssistantReply) -> None:
    if not reply.hits:
        return
    st.markdown("#### Sources")
    cited = set(reply.cited_source_numbers)
    for number, hit in enumerate(reply.hits, start=1):
        st.markdown(f'<span id="source-{number}"></span>', unsafe_allow_html=True)
        source = hit.chunk.source
        page = source.printed_page or f"physical page {source.physical_page}"
        with st.container(border=True):
            label = "CITED SOURCE" if number in cited else "RETRIEVED EVIDENCE"
            st.markdown(f'<div class="source-label">{label} · {number}</div>', unsafe_allow_html=True)
            st.markdown(f"**{hit.chunk.title}**  \nAMU Guide to Admissions 2026–27 · Page **{page}**")
            st.markdown(
                f'<div class="source-preview">{html.escape(context_preview(hit.chunk.text))}</div>',
                unsafe_allow_html=True,
            )
            with st.expander("View complete retrieved context"):
                st.text(hit.chunk.text)


def render_reply(reply: AssistantReply) -> None:
    linked_answer = link_answer_citations(reply.answer, reply.cited_source_numbers)
    st.markdown(linked_answer)
    if reply.citation_warning:
        st.warning(reply.citation_warning)
    with st.expander("How this answer was found"):
        st.markdown(f"**Expanded query:** {reply.query.expanded_query}")
        st.markdown(f"**Retrieval mode:** {reply.retrieval_mode.replace('_', ' ').title()}")
        st.markdown(f"**Model:** `{reply.model}`")
        if reply.citation_repair_attempted:
            st.caption("A citation-validation pass was applied before displaying this answer.")
        if reply.eligibility_repair_attempted:
            st.caption("An eligibility-safety pass was applied to avoid inferring unstated applicant details.")
    render_sources(reply)


with st.sidebar:
    st.markdown("### 🎓 AMU Guide Assistant")
    st.caption("Guide to Admissions 2026–27")
    st.markdown(
        '<div class="coverage-note"><strong>Validated coverage</strong><br>'
        f"{html.escape(coverage_text(approved_coverage()))}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown("**Answer model**  \n`openai/gpt-oss-20b`")
    st.markdown("**Retrieval**  \nHybrid BM25 + vector + RRF")
    st.markdown("**Evidence policy**  \nHuman-approved chunks only")
    guide_path = AppPaths.from_package().source_pdf
    if guide_path.exists():
        st.download_button(
            "Download admissions guide",
            data=guide_path.read_bytes(),
            file_name="AMU-Guide-to-Admissions-2026-27.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.markdown(
    """
    <section class="hero">
      <div class="hero-kicker">HUMAN-VALIDATED ADMISSIONS RAG</div>
      <h1>Ask the AMU Admissions Guide</h1>
      <p>Explore eligibility, course details, intake, selection processes and test information with answers grounded in the official guide.</p>
      <div class="trust-row">
        <span class="trust-pill">✓ In-text citations</span>
        <span class="trust-pill">✓ Page-level sources</span>
        <span class="trust-pill">✓ Abbreviation aware</span>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []

submitted_query: str | None = None
if not st.session_state.messages:
    st.markdown("#### Try an example")
    columns = st.columns(2)
    for index, example in enumerate(EXAMPLE_QUESTIONS):
        if columns[index % 2].button(example, key=f"example-{index}", use_container_width=True):
            submitted_query = example

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_reply(message["reply"])
        else:
            st.markdown(message["content"])

chat_query = st.chat_input("Ask about courses, eligibility, intake, selection or tests…")
submitted_query = chat_query or submitted_query

if submitted_query:
    st.session_state.messages.append({"role": "user", "content": submitted_query})
    with st.chat_message("user"):
        st.markdown(submitted_query)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching the validated guide and preparing a cited answer…"):
                assistant = load_assistant()
                reply = assistant.ask(submitted_query)
            render_reply(reply)
            st.session_state.messages.append({"role": "assistant", "reply": reply})
        except Exception as error:
            st.error("The assistant could not complete this request. Please try again.")
            st.caption(str(error))
