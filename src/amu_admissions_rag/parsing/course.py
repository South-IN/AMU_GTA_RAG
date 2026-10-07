"""Convert extracted course-page layouts into reviewable course records."""

from __future__ import annotations

import re
from dataclasses import dataclass

from amu_admissions_rag.models import (
    BoundingBox,
    CourseCorpus,
    CourseField,
    CourseRecord,
    CourseTable,
    CourseTableCell,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
    ExtractedTextLine,
    ProgramLevel,
    SourceReference,
)


@dataclass(frozen=True)
class _CourseAnchor:
    top: float
    name: str


FIELD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("course_of_study", re.compile(r"^Courses? of Study\b\s*:?", re.IGNORECASE)),
    ("course_details", re.compile(r"^Course Details\b\s*:?", re.IGNORECASE)),
    (
        "qualifying_examination",
        re.compile(r"^Qualifying(?:\s+Examination)?\b\s*:?", re.IGNORECASE),
    ),
    ("age_limit", re.compile(r"^Age Limit\b\s*:?", re.IGNORECASE)),
    (
        "selection_process",
        re.compile(r"^Selection(?:\s+Process)?\b\s*:?", re.IGNORECASE),
    ),
    (
        "test_paper_details",
        re.compile(
            r"^(?:Test Paper(?:\s+Details)?|Test Details)\b\s*:?",
            re.IGNORECASE,
        ),
    ),
    (
        "test_centres",
        re.compile(r"^Test Centre(?:\(s\)|s)?\s*:?", re.IGNORECASE),
    ),
    (
        "additional_information",
        re.compile(r"^Additional(?:\s+Information)?\b\s*:?", re.IGNORECASE),
    ),
    ("specialization", re.compile(r"^Specialization\b\s*:?", re.IGNORECASE)),
    ("remarks", re.compile(r"^Remarks\b\s*:?", re.IGNORECASE)),
)

FIELD_LABELS = {
    "qualifying_examination": "Qualifying Examination",
    "age_limit": "Age Limit",
    "selection_process": "Selection Process",
    "test_paper_details": "Test Paper Details",
    "test_centres": "Test Centre(s)",
    "additional_information": "Additional Information",
    "specialization": "Specialization",
    "remarks": "Remarks",
}

SPLIT_FIELD_LABELS = {
    "qualifying_examination": re.compile(r"^Examination\b\s*:?", re.IGNORECASE),
    "selection_process": re.compile(r"^Process\b\s*:?", re.IGNORECASE),
    "test_paper_details": re.compile(r"^Details\b\s*:?", re.IGNORECASE),
    "additional_information": re.compile(r"^Information\b\s*:?", re.IGNORECASE),
}

HEADER_ALIASES = {
    "duration": "duration",
    "specialization": "specialization",
    "course code": "course_code",
    "code": "course_code",
    "intake": "intake",
    "study location": "study_location",
    "branch name": "branch_name",
    "major subject": "major_subject",
    "discipline /department": "discipline",
    "discipline/department": "discipline",
    "discipline": "discipline",
    # Medical PG tables list each specialty under a "Course of Study" column.
    "course of study": "specialization",
    "course of study/specialization": "specialization",
    "faculty": "faculty",
    "male": "intake_male",
    "males": "intake_male",
    "female": "intake_female",
    "females": "intake_female",
    "general": "intake_general",
    "pwbd": "intake_pwbd",
}

PROGRAM_LEVEL_BY_PREFIX = {
    "A": ProgramLevel.UNDERGRADUATE,
    "B": ProgramLevel.POSTGRADUATE,
    "C": ProgramLevel.RESEARCH,
    "D": ProgramLevel.DIPLOMA,
    "E": ProgramLevel.SCHOOL,
    "F": ProgramLevel.BRIDGE,
    "G": ProgramLevel.DIPLOMA,
    "H": ProgramLevel.OTHER,
    "I": ProgramLevel.CERTIFICATE,
}


class CourseParser:
    """Parse repeated course cards while retaining source provenance."""

    def parse(
        self,
        extracted: ExtractedDocument,
        *,
        initial_faculty: str | None = None,
    ) -> CourseCorpus:
        courses: list[CourseRecord] = []
        current_faculty = initial_faculty
        previous_physical_page: int | None = None

        for page in sorted(extracted.pages, key=lambda item: item.physical_page):
            if (
                courses
                and previous_physical_page is not None
                and page.physical_page == previous_physical_page + 1
            ):
                courses[-1] = self._extend_previous_course(
                    extracted.document.document_id,
                    page,
                    courses[-1],
                )
            page_courses, current_faculty = self._parse_page(
                extracted.document.document_id,
                page,
                current_faculty,
            )
            courses.extend(page_courses)
            previous_physical_page = page.physical_page

        return CourseCorpus(document=extracted.document, courses=courses)

    def _extend_previous_course(
        self,
        document_id: str,
        page: ExtractedPage,
        course: CourseRecord,
    ) -> CourseRecord:
        """Attach a leading cross-page fragment to the preceding course card."""

        end_top = self._leading_continuation_end(page)
        fragment_lines = [
            line
            for line in page.lines
            if line.bounding_box.top < end_top and not self._is_noise(line.text)
        ]
        if not self._is_course_continuation(page, course, fragment_lines):
            return course

        initial_field_name = course.fields[-1].name if course.fields else None
        continuation_fields = self._extract_fields(
            document_id=document_id,
            page=page,
            start_top=0,
            end_top=end_top,
            initial_field_name=initial_field_name,
            source_printed_page=course.source.printed_page,
            source_section=course.faculty,
        )
        if not continuation_fields:
            return course

        merged_fields = list(course.fields)
        for continuation in continuation_fields:
            existing_index = next(
                (
                    index
                    for index, existing in enumerate(merged_fields)
                    if existing.name == continuation.name
                ),
                None,
            )
            if existing_index is None:
                merged_fields.append(continuation)
                continue

            existing = merged_fields[existing_index]
            source = existing.source
            if source.physical_page != continuation.source.physical_page:
                source = source.model_copy(update={"bounding_box": None})
            merged_fields[existing_index] = existing.model_copy(
                update={
                    "value": self._clean_text(
                        f"{existing.value} {continuation.value}"
                    ),
                    "source": source,
                }
            )

        return course.model_copy(update={"fields": merged_fields})

    def _leading_continuation_end(self, page: ExtractedPage) -> float:
        boundaries: list[float] = []
        for line in page.lines:
            text = line.text.strip()
            if self._is_noise(text):
                continue
            if (
                re.match(r"^Courses? of Study\b", text, re.IGNORECASE)
                or re.match(r"^Course Details\b", text, re.IGNORECASE)
                or text.lower().startswith("faculty of ")
                or text.upper().endswith("PROGRAMMES")
                or (line.max_font_size is not None and line.max_font_size >= 13)
            ):
                boundaries.append(line.bounding_box.top)
        return min(boundaries, default=page.height)

    def _is_course_continuation(
        self,
        page: ExtractedPage,
        course: CourseRecord,
        lines: list[ExtractedTextLine],
    ) -> bool:
        if not lines:
            return False

        has_field_label = any(
            field_name in FIELD_LABELS and pattern.match(line.text.strip())
            for line in lines
            for field_name, pattern in FIELD_PATTERNS
        )
        if has_field_label:
            return True

        if not course.fields:
            return False
        first_line = min(lines, key=lambda item: item.bounding_box.top)
        return (
            first_line.bounding_box.top <= 90
            and first_line.bounding_box.x0 >= page.width * 0.15
            and (
                first_line.max_font_size is None
                or first_line.max_font_size <= 11
            )
        )

    def _parse_page(
        self,
        document_id: str,
        page: ExtractedPage,
        current_faculty: str | None,
    ) -> tuple[list[CourseRecord], str | None]:
        anchors = self._course_anchors(page)
        if not anchors:
            return [], self._last_faculty(page.lines) or current_faculty

        faculty_lines = [
            line for line in page.lines if line.text.strip().lower().startswith("faculty of ")
        ]
        page_level = self._program_level(page.printed_page)
        results: list[CourseRecord] = []

        for index, anchor in enumerate(anchors):
            end_top = anchors[index + 1].top if index + 1 < len(anchors) else page.height
            local_faculty = self._faculty_before(faculty_lines, anchor.top) or current_faculty
            if local_faculty is None:
                local_faculty = "Faculty not resolved"

            source = SourceReference(
                document_id=document_id,
                physical_page=page.physical_page,
                printed_page=page.printed_page,
                section=local_faculty,
            )
            fields = self._extract_fields(
                document_id=document_id,
                page=page,
                start_top=anchor.top,
                end_top=end_top,
            )
            tables = self._extract_course_tables(
                document_id=document_id,
                page=page,
                start_top=anchor.top,
                end_top=end_top,
            )
            # Narrative uses of "Course of Study" can resemble a course-card
            # heading. A real guide card must contribute at least one parsed
            # field or one normalized course-details table.
            if not fields and not tables:
                continue

            course_code = self._single_course_code(tables)
            results.append(
                CourseRecord(
                    record_id=self._record_id(
                        document_id,
                        page.physical_page,
                        anchor.name,
                        index,
                    ),
                    document_id=document_id,
                    course_name=anchor.name,
                    course_code=course_code,
                    program_level=page_level,
                    faculty=local_faculty,
                    source=source,
                    fields=fields,
                    tables=tables,
                )
            )

            following_faculty = self._faculty_before(faculty_lines, end_top)
            if following_faculty:
                current_faculty = following_faculty

        return results, self._last_faculty(page.lines) or current_faculty

    def _course_anchors(self, page: ExtractedPage) -> list[_CourseAnchor]:
        line_anchors: list[_CourseAnchor] = []
        for index, line in enumerate(page.lines):
            # Some pages (e.g. medical PG programmes) use the plural heading.
            if not re.match(r"^Courses? of Study\b", line.text.strip(), re.IGNORECASE):
                continue
            name = self._course_name_from_line(page.lines, index)
            if name:
                line_anchors.append(_CourseAnchor(top=line.bounding_box.top, name=name))

        table_candidates = self._table_course_names(page.tables)
        enhanced: list[_CourseAnchor] = []
        for anchor in line_anchors:
            nearby = [
                candidate
                for candidate in table_candidates
                if abs(candidate.top - anchor.top) <= 80
                and self._names_overlap(anchor.name, candidate.name)
            ]
            if nearby:
                best = min(nearby, key=lambda candidate: abs(candidate.top - anchor.top))
                name = best.name if len(best.name) > len(anchor.name) else anchor.name
                enhanced.append(_CourseAnchor(top=anchor.top, name=name))
            else:
                enhanced.append(anchor)
        return sorted(enhanced, key=lambda item: item.top)

    def _course_name_from_line(
        self,
        lines: list[ExtractedTextLine],
        index: int,
    ) -> str | None:
        line = lines[index]
        match = re.match(
            r"^Courses? of Study\b\s*:?[\s]*(.*)$",
            line.text.strip(),
            re.IGNORECASE,
        )
        remainder = match.group(1).strip(" :") if match else ""

        if not remainder:
            nearby = [
                candidate
                for candidate in lines[max(0, index - 3) : index + 4]
                if abs(candidate.bounding_box.top - line.bounding_box.top) <= 20
                and candidate.text.strip().startswith(":")
            ]
            if nearby:
                remainder = nearby[0].text.strip().lstrip(":").strip()

        if remainder:
            following = lines[index + 1 : index + 4]
            scheme = next(
                (
                    candidate.text.strip()
                    for candidate in following
                    if abs(candidate.bounding_box.top - line.bounding_box.top) <= 22
                    and "Self Financing Scheme" in candidate.text
                ),
                None,
            )
            if scheme and scheme not in remainder:
                remainder = f"{remainder} {scheme}"
        return self._clean_text(remainder) or None

    def _table_course_names(self, tables: list[ExtractedTable]) -> list[_CourseAnchor]:
        candidates: list[_CourseAnchor] = []
        for table in tables:
            flattened = [cell for row in table.rows for cell in row if cell]
            for index, cell in enumerate(flattened):
                if cell.strip().lower() not in {"course of study", "courses of study"}:
                    continue
                for candidate in flattened[index + 1 :]:
                    normalized = candidate.strip(" :")
                    if not normalized or normalized.lower() == "course details":
                        continue
                    candidates.append(
                        _CourseAnchor(
                            top=table.bounding_box.top,
                            name=self._clean_text(normalized),
                        )
                    )
                    break
        return candidates

    def _extract_fields(
        self,
        *,
        document_id: str,
        page: ExtractedPage,
        start_top: float,
        end_top: float,
        initial_field_name: str | None = None,
        source_printed_page: str | None = None,
        source_section: str | None = None,
    ) -> list[CourseField]:
        lines = [
            line
            for line in page.lines
            if start_top <= line.bounding_box.top < end_top and not self._is_noise(line.text)
        ]
        collected: dict[str, list[ExtractedTextLine]] = {}
        current_name = initial_field_name
        if current_name is not None:
            collected[current_name] = []

        for line in lines:
            matched_name: str | None = None
            remainder = ""
            for field_name, pattern in FIELD_PATTERNS:
                match = pattern.match(line.text.strip())
                if match:
                    matched_name = field_name
                    remainder = line.text.strip()[match.end() :].strip(" :")
                    break

            if matched_name:
                current_name = matched_name
                collected.setdefault(current_name, [])
                if remainder:
                    collected[current_name].append(
                        self._line_with_text(line, remainder)
                    )
            elif current_name:
                cleaned_line = self._remove_split_field_label(
                    current_name,
                    line,
                    page.width,
                )
                if cleaned_line is not None:
                    collected[current_name].append(cleaned_line)

        fields: list[CourseField] = []
        for name, field_lines in collected.items():
            if name not in FIELD_LABELS or not field_lines:
                continue
            value = self._clean_text(" ".join(line.text for line in field_lines))
            if not value:
                continue
            box = self._union_boxes([line.bounding_box for line in field_lines])
            fields.append(
                CourseField(
                    name=name,
                    label=FIELD_LABELS[name],
                    value=value,
                    source=SourceReference(
                        document_id=document_id,
                        physical_page=page.physical_page,
                        printed_page=source_printed_page or page.printed_page,
                        section=source_section,
                        bounding_box=box,
                    ),
                )
            )
        return fields

    def _extract_course_tables(
        self,
        *,
        document_id: str,
        page: ExtractedPage,
        start_top: float,
        end_top: float,
    ) -> list[CourseTable]:
        normalized: list[CourseTable] = []
        for table in page.tables:
            if not (start_top <= table.bounding_box.top < end_top):
                continue
            converted = self._normalize_table(document_id, page, table)
            if converted:
                normalized.append(converted)
        return normalized

    def _normalize_table(
        self,
        document_id: str,
        page: ExtractedPage,
        table: ExtractedTable,
    ) -> CourseTable | None:
        positions: dict[str, int] = {}
        header_end = -1

        for row_index, row in enumerate(table.rows[:3]):
            for column_index, cell in enumerate(row):
                if not cell:
                    continue
                key = HEADER_ALIASES.get(self._normalize_header(cell))
                if key:
                    positions[key] = column_index
                    header_end = max(header_end, row_index)

        if len(positions) < 2:
            return None
        if "intake_male" in positions or "intake_female" in positions:
            positions.pop("intake", None)

        ordered_headers = [
            key for key, _ in sorted(positions.items(), key=lambda item: item[1])
        ]
        rows: list[dict[str, CourseTableCell]] = []
        inherited_values: dict[str, str] = {}
        forward_fill = {
            "duration",
            "intake",
            "intake_male",
            "intake_female",
            "intake_general",
            "intake_pwbd",
            "faculty",
        }

        for raw_row in table.rows[header_end + 1 :]:
            values = self._map_row_to_headers(raw_row, positions)
            if not any(values.values()):
                continue

            cells: dict[str, CourseTableCell] = {}
            for header in ordered_headers:
                value = values.get(header)
                inherited = False
                if not value and header in forward_fill and header in inherited_values:
                    value = inherited_values[header]
                    inherited = True
                if value:
                    cells[header] = CourseTableCell(text=value, inherited=inherited)
                    if header in forward_fill and not inherited:
                        inherited_values[header] = value

            identifying_headers = {
                "course_code",
                "specialization",
                "study_location",
                "branch_name",
                "major_subject",
                "discipline",
            }
            if cells and (
                identifying_headers.intersection(cells)
                or "duration" in cells
                or "intake" in cells
                or "intake_male" in cells
            ):
                rows.append(cells)

        if not rows:
            return None

        return CourseTable(
            name="course_details",
            headers=ordered_headers,
            rows=rows,
            source=SourceReference(
                document_id=document_id,
                physical_page=page.physical_page,
                printed_page=page.printed_page,
                bounding_box=table.bounding_box,
            ),
        )

    def _map_row_to_headers(
        self,
        row: list[str | None],
        positions: dict[str, int],
    ) -> dict[str, str | None]:
        mapped: dict[str, list[str]] = {key: [] for key in positions}
        for column_index, value in enumerate(row):
            if not value:
                continue
            nearest = min(
                positions,
                key=lambda key: abs(positions[key] - column_index),
            )
            mapped[nearest].append(value)
        return {
            key: self._clean_text(" ".join(values)) if values else None
            for key, values in mapped.items()
        }

    @staticmethod
    def _faculty_before(
        faculty_lines: list[ExtractedTextLine],
        top: float,
    ) -> str | None:
        before = [line.text.strip() for line in faculty_lines if line.bounding_box.top < top]
        return before[-1] if before else None

    @staticmethod
    def _last_faculty(lines: list[ExtractedTextLine]) -> str | None:
        faculties = [
            line.text.strip()
            for line in lines
            if line.text.strip().lower().startswith("faculty of ")
        ]
        return faculties[-1] if faculties else None

    @staticmethod
    def _program_level(printed_page: str | None) -> ProgramLevel:
        if not printed_page:
            return ProgramLevel.OTHER
        return PROGRAM_LEVEL_BY_PREFIX.get(printed_page[0].upper(), ProgramLevel.OTHER)

    @staticmethod
    def _single_course_code(tables: list[CourseTable]) -> str | None:
        codes = {
            row["course_code"].text
            for table in tables
            for row in table.rows
            if "course_code" in row
        }
        return next(iter(codes)) if len(codes) == 1 else None

    @staticmethod
    def _normalize_header(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().lower()

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _is_noise(value: str) -> bool:
        text = value.strip()
        lowered = text.lower()
        return (
            lowered
            in {
                "aligarh muslim university",
                "guide to admissions 2026-27",
                "aligarh muslim university guide to admissions 2026-27",
            }
            or lowered.startswith("faculty of ")
            or lowered.endswith(" programmes")
            or bool(re.fullmatch(r"[A-K]\.\d+", text, re.IGNORECASE))
        )

    @staticmethod
    def _line_with_text(line: ExtractedTextLine, text: str) -> ExtractedTextLine:
        return line.model_copy(update={"text": text})

    @classmethod
    def _remove_split_field_label(
        cls,
        field_name: str,
        line: ExtractedTextLine,
        page_width: float,
    ) -> ExtractedTextLine | None:
        pattern = SPLIT_FIELD_LABELS.get(field_name)
        if pattern is None or line.bounding_box.x0 > page_width * 0.12:
            return line
        text = pattern.sub("", line.text.strip(), count=1).strip(" :")
        if not text:
            return None
        return cls._line_with_text(line, text)

    @staticmethod
    def _union_boxes(boxes: list[BoundingBox]) -> BoundingBox:
        return BoundingBox(
            x0=min(box.x0 for box in boxes),
            top=min(box.top for box in boxes),
            x1=max(box.x1 for box in boxes),
            bottom=max(box.bottom for box in boxes),
        )

    @staticmethod
    def _names_overlap(left: str, right: str) -> bool:
        left_tokens = set(re.findall(r"[a-z0-9]+", left.lower()))
        right_tokens = set(re.findall(r"[a-z0-9]+", right.lower()))
        if not left_tokens or not right_tokens:
            return False
        overlap = len(left_tokens & right_tokens)
        return overlap / min(len(left_tokens), len(right_tokens)) >= 0.6

    @staticmethod
    def _record_id(
        document_id: str,
        physical_page: int,
        course_name: str,
        index: int,
    ) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", course_name.lower()).strip("-")
        return f"{document_id}:{physical_page}:{index + 1}:{slug[:72]}"
