"""Build approval-gated, self-contained retrieval chunks."""

from __future__ import annotations

from collections.abc import Iterable

from amu_admissions_rag.models import (
    AppendixRecord,
    AppendixType,
    ChunkType,
    CourseCorpus,
    CourseField,
    CourseRecord,
    CourseTable,
    IndexCorpus,
    PolicyCorpus,
    RetrievalChunk,
    ReviewStatus,
    SectionRecord,
)


class RetrievalChunkBuilder:
    """Convert reviewed source records into focused retrieval documents."""

    def build(
        self,
        course_corpus: CourseCorpus,
        policy_corpus: PolicyCorpus,
        *,
        include_pending: bool = False,
    ) -> IndexCorpus:
        if course_corpus.document.document_id != policy_corpus.document.document_id:
            raise ValueError("course and policy corpora must belong to the same document")

        chunks: list[RetrievalChunk] = []
        for course in course_corpus.courses:
            if not self._eligible(course.review.status, include_pending):
                continue
            chunks.extend(self._course_chunks(course))

        for section in policy_corpus.sections:
            if not self._eligible(section.review.status, include_pending):
                continue
            chunks.append(self._policy_chunk(section))

        for appendix_row in policy_corpus.appendix_rows:
            if not self._eligible(appendix_row.review.status, include_pending):
                continue
            chunks.append(self._appendix_chunk(appendix_row))

        return IndexCorpus(document=course_corpus.document, chunks=chunks)

    def _course_chunks(self, course: CourseRecord) -> list[RetrievalChunk]:
        chunks = [self._course_overview_chunk(course)]
        chunks.extend(self._course_field_chunk(course, field) for field in course.fields)
        for table_index, table in enumerate(course.tables, start=1):
            chunks.extend(self._course_table_chunks(course, table, table_index))
        return chunks

    def _course_overview_chunk(self, course: CourseRecord) -> RetrievalChunk:
        lines = self._course_context(course)
        lines.extend(
            [
                "Record Type: Course Overview",
                "Available Fields: "
                + ", ".join(field.label for field in course.fields),
            ]
        )
        if course.tables:
            lines.append(
                "Available Tables: "
                + ", ".join(self._display_name(table.name) for table in course.tables)
            )
        return RetrievalChunk(
            chunk_id=f"{course.record_id}:overview",
            document_id=course.document_id,
            chunk_type=ChunkType.COURSE_OVERVIEW,
            parent_record_id=course.record_id,
            title=f"{course.course_name} - Overview",
            text="\n".join(lines),
            source=course.source,
            metadata=self._course_metadata(course),
            review=course.review,
        )

    def _course_field_chunk(
        self,
        course: CourseRecord,
        field: CourseField,
    ) -> RetrievalChunk:
        lines = self._course_context(course)
        lines.extend([f"Field: {field.label}", "", field.value])
        return RetrievalChunk(
            chunk_id=f"{course.record_id}:field:{field.name}",
            document_id=course.document_id,
            chunk_type=ChunkType.COURSE_FIELD,
            parent_record_id=course.record_id,
            title=f"{course.course_name} - {field.label}",
            text="\n".join(lines),
            source=field.source,
            field_name=field.name,
            metadata=self._course_metadata(course),
            review=course.review,
        )

    def _course_table_chunks(
        self,
        course: CourseRecord,
        table: CourseTable,
        table_index: int,
    ) -> Iterable[RetrievalChunk]:
        for row_index, row in enumerate(table.rows, start=1):
            lines = self._course_context(course)
            lines.extend(
                [
                    f"Table: {self._display_name(table.name)}",
                    f"Table Row: {row_index}",
                    "",
                ]
            )
            for header in table.headers:
                cell = row.get(header)
                if cell is not None:
                    lines.append(f"{self._display_name(header)}: {cell.text}")
            yield RetrievalChunk(
                chunk_id=(
                    f"{course.record_id}:table:{table_index}:row:{row_index}"
                ),
                document_id=course.document_id,
                chunk_type=ChunkType.COURSE_TABLE_ROW,
                parent_record_id=course.record_id,
                title=(
                    f"{course.course_name} - "
                    f"{self._display_name(table.name)} row {row_index}"
                ),
                text="\n".join(lines),
                source=table.source,
                field_name=table.name,
                metadata=self._course_metadata(course),
                review=course.review,
            )

    def _policy_chunk(self, section: SectionRecord) -> RetrievalChunk:
        lines = [f"Section: {section.heading}"]
        if section.heading_path:
            lines.append(f"Section Path: {' > '.join(section.heading_path)}")
        lines.extend(["", section.text])
        return RetrievalChunk(
            chunk_id=f"{section.record_id}:chunk",
            document_id=section.document_id,
            chunk_type=ChunkType.POLICY_SECTION,
            parent_record_id=section.record_id,
            title=section.heading,
            text="\n".join(lines),
            source=section.source,
            metadata={"heading": section.heading},
            review=section.review,
        )

    def _appendix_chunk(self, record: AppendixRecord) -> RetrievalChunk:
        lines = [
            f"Course: {record.course_name}",
            f"Record Type: {self._appendix_label(record.appendix_type)}",
        ]
        if record.course_code:
            lines.append(f"Course Code: {record.course_code}")
        if record.faculty:
            lines.append(f"Faculty or Unit: {record.faculty}")
        if record.programme_group:
            lines.append(f"Programme Group: {record.programme_group}")
        if record.category:
            lines.append(f"Category: {record.category}")
        lines.append("")
        lines.extend(
            f"{self._display_name(name)}: {cell.text}"
            for name, cell in record.values.items()
        )
        metadata: dict[str, str | int | float | bool | None] = {
            "appendix_type": record.appendix_type.value,
            "course_name": record.course_name,
            "course_code": record.course_code,
            "faculty": record.faculty,
            "programme_group": record.programme_group,
            "category": record.category,
        }
        return RetrievalChunk(
            chunk_id=f"{record.record_id}:chunk",
            document_id=record.document_id,
            chunk_type=ChunkType.APPENDIX_ROW,
            parent_record_id=record.record_id,
            title=(
                f"{record.course_name} - "
                f"{self._appendix_label(record.appendix_type)}"
            ),
            text="\n".join(lines),
            source=record.source,
            field_name=record.appendix_type.value,
            metadata=metadata,
            review=record.review,
        )

    @staticmethod
    def _eligible(status: ReviewStatus, include_pending: bool) -> bool:
        return status is ReviewStatus.APPROVED or (
            include_pending and status is ReviewStatus.PENDING
        )

    @staticmethod
    def _course_context(course: CourseRecord) -> list[str]:
        lines = [f"Course: {course.course_name}"]
        if course.course_code:
            lines.append(f"Course Code: {course.course_code}")
        lines.extend(
            [
                f"Faculty: {course.faculty}",
                f"Programme Level: {course.program_level.value}",
            ]
        )
        if course.campus:
            lines.append(f"Campus: {course.campus}")
        return lines

    @staticmethod
    def _course_metadata(
        course: CourseRecord,
    ) -> dict[str, str | int | float | bool | None]:
        return {
            "course_name": course.course_name,
            "course_code": course.course_code,
            "faculty": course.faculty,
            "program_level": course.program_level.value,
            "campus": course.campus,
        }

    @staticmethod
    def _display_name(value: str) -> str:
        return value.replace("_", " ").strip().title()

    @staticmethod
    def _appendix_label(appendix_type: AppendixType) -> str:
        return {
            AppendixType.APPLICATION_SUMMARY: "Application Form Details",
            AppendixType.TEST_SCHEDULE: "Admission Test Schedule",
            AppendixType.FEE_SUMMARY: "Admission Fee",
        }[appendix_type]
