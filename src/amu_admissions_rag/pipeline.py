"""End-to-end ingestion: PDF -> pending corpora -> human review -> approved index."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.corpus import APPROVED_INDEX_NAME, REVIEWED_COURSES_NAME
from amu_admissions_rag.extraction import PdfExtractor
from amu_admissions_rag.indexing import RetrievalChunkBuilder
from amu_admissions_rag.models import ExtractedDocument, ReviewBatch
from amu_admissions_rag.parsing import CourseParser, PolicyParser
from amu_admissions_rag.reviews import apply_review_batches
from amu_admissions_rag.storage import IngestionRun, PostgresIndexStore

COURSE_PAGES = range(54, 128)
FULL_EXTRACTION_NAME = "guide-2026-27.full-extraction.json"
PENDING_COURSES_NAME = "guide-2026-27.course-corpus.pending.json"
PENDING_POLICIES_NAME = "guide-2026-27.policy-corpus.pending.json"
REVIEWED_POLICIES_NAME = "guide-2026-27.policy-corpus.reviewed.json"


@dataclass(frozen=True)
class PipelineResult:
    skipped: bool
    fingerprint: str
    approved_chunks: int | None = None


def pipeline_version() -> str:
    try:
        return version("amu-admissions-rag")
    except PackageNotFoundError:
        return "unknown"


def load_review_batches(reviews_dir: Path) -> list[tuple[Path, ReviewBatch]]:
    """Load every review batch, oldest first, so later decisions win."""

    batches = [
        (path, ReviewBatch.model_validate_json(path.read_text(encoding="utf-8")))
        for path in sorted(reviews_dir.glob("*.json"))
    ]
    return sorted(batches, key=lambda item: (item[1].reviewed_at, item[0].name))


def ingestion_fingerprint(pdf_sha256: str, paths: AppPaths, reviews_dir: Path) -> str:
    """Hash every input that can change the loaded corpus.

    The source PDF, parser/indexing code, SQL migrations and review batches are
    included, so the pipeline re-runs when any of them changes and is skipped
    otherwise.
    """

    digest = hashlib.sha256()
    digest.update(f"pdf:{pdf_sha256}\nversion:{pipeline_version()}\n".encode())
    package_dir = Path(__file__).resolve().parent
    inputs = [
        *(("code", path, path.relative_to(package_dir)) for path in package_dir.rglob("*.py")),
        *(("sql", path, path.name) for path in (paths.project_root / "sql").glob("*.sql")),
        *(("review", path, path.name) for path in reviews_dir.glob("*.json")),
    ]
    for kind, path, name in sorted(inputs, key=lambda item: (item[0], str(item[2]))):
        digest.update(f"{kind}:{name}:".encode())
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"\n")
    return digest.hexdigest()


def run_pipeline(
    *,
    paths: AppPaths,
    database_url: str | None,
    reviews_dir: Path,
    force: bool = False,
    log=print,
) -> PipelineResult:
    extractor = PdfExtractor(paths.source_pdf)
    document = extractor.document_record()
    fingerprint = ingestion_fingerprint(document.sha256, paths, reviews_dir)
    store = PostgresIndexStore(database_url) if database_url else None

    if store is not None:
        applied = store.apply_migrations(paths.project_root / "sql")
        log(f"Migrations applied: {', '.join(applied) if applied else 'none pending'}")
        if not force and store.latest_ingestion_fingerprint(document.document_id) == fingerprint:
            log("Corpus is up to date (inputs unchanged since the last load); skipping.")
            return PipelineResult(skipped=True, fingerprint=fingerprint)

    paths.ensure_output_directories()
    log(f"Extracting {document.total_pages} pages from {paths.source_pdf.name}...")
    extracted = extractor.extract_pages(range(1, document.total_pages + 1))
    _write(paths.processed_dir / FULL_EXTRACTION_NAME, extracted)

    course_pages = ExtractedDocument(
        document=extracted.document,
        pages=[page for page in extracted.pages if page.physical_page in COURSE_PAGES],
    )
    courses = CourseParser().parse(course_pages)
    policies = PolicyParser().parse(extracted)
    _write(paths.review_dir / PENDING_COURSES_NAME, courses)
    _write(paths.review_dir / PENDING_POLICIES_NAME, policies)
    log(
        f"Parsed {len(courses.courses)} course record(s), {len(policies.sections)} policy "
        f"chunk(s) and {len(policies.appendix_rows)} appendix row(s), all pending review"
    )

    batches = load_review_batches(reviews_dir)
    courses, policies = apply_review_batches(
        courses, policies, [batch for _, batch in batches]
    )
    _write(paths.review_dir / REVIEWED_COURSES_NAME, courses)
    _write(paths.review_dir / REVIEWED_POLICIES_NAME, policies)
    decisions = sum(len(batch.decisions) for _, batch in batches)
    log(f"Applied {decisions} human-review decision(s) from {len(batches)} batch file(s)")

    index = RetrievalChunkBuilder().build(courses, policies)
    _write(paths.processed_dir / APPROVED_INDEX_NAME, index)
    log(f"Built {len(index.chunks)} approved retrieval chunk(s)")

    if store is None:
        log("AMU_RAG_DATABASE_URL is not set; wrote local JSON artifacts only.")
        return PipelineResult(
            skipped=False, fingerprint=fingerprint, approved_chunks=len(index.chunks)
        )

    loaded = store.replace_approved_corpus(
        courses,
        policies,
        ingestion=IngestionRun(
            fingerprint=fingerprint,
            pipeline_version=pipeline_version(),
            review_batches=[
                {
                    "file": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "reviewer": batch.reviewer,
                    "reviewed_at": batch.reviewed_at.isoformat(),
                }
                for path, batch in batches
            ],
        ),
    )
    log(f"Loaded {loaded} approved retrieval chunk(s) into PostgreSQL")
    return PipelineResult(skipped=False, fingerprint=fingerprint, approved_chunks=loaded)


def _write(path: Path, model) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
