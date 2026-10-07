"""Create a human-readable course corpus without extraction metadata."""

from __future__ import annotations

from typing import Any

from amu_admissions_rag.models import CourseCorpus, CourseTableCell, SourceReference


def _source_payload(source: SourceReference) -> dict[str, Any]:
    payload: dict[str, Any] = {"physical_page": source.physical_page}
    if source.printed_page is not None:
        payload["printed_page"] = source.printed_page
    if source.section is not None:
        payload["section"] = source.section
    return payload


def _cell_payload(cell: CourseTableCell) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": cell.text,
        "inherited": cell.inherited,
    }
    if cell.source is not None:
        payload["source"] = _source_payload(cell.source)
    return payload


def build_human_review_payload(corpus: CourseCorpus) -> dict[str, Any]:
    """Retain reviewable content while removing technical extraction metadata."""

    courses: list[dict[str, Any]] = []
    for course in corpus.courses:
        courses.append(
            {
                "course_name": course.course_name,
                "program_level": course.program_level.value,
                "faculty": course.faculty,
                "course_code": course.course_code,
                "campus": course.campus,
                "source": _source_payload(course.source),
                "fields": [
                    {
                        "name": field.name,
                        "label": field.label,
                        "value": field.value,
                        "source": _source_payload(field.source),
                    }
                    for field in course.fields
                ],
                "tables": [
                    {
                        "name": table.name,
                        "headers": table.headers,
                        "rows": [
                            {
                                header: _cell_payload(cell)
                                for header, cell in row.items()
                            }
                            for row in table.rows
                        ],
                        "source": _source_payload(table.source),
                    }
                    for table in course.tables
                ],
                "review": course.review.model_dump(mode="json"),
            }
        )

    return {
        "guide": {
            "filename": corpus.document.filename,
            "academic_year": corpus.document.academic_year,
            "total_pages": corpus.document.total_pages,
        },
        "courses": courses,
    }
