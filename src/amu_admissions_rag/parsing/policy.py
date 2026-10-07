"""Create reviewable policy chunks and normalized appendix rows."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from amu_admissions_rag.models import (
    AppendixCell,
    AppendixRecord,
    AppendixType,
    BoundingBox,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTextLine,
    PolicyCorpus,
    SectionRecord,
    SourceReference,
)


POLICY_PAGE_RANGES: tuple[range, ...] = (range(19, 54), range(164, 172), range(187, 188))
APPENDIX_PAGE_RANGES: dict[AppendixType, range] = {
    AppendixType.APPLICATION_SUMMARY: range(128, 149),
    AppendixType.TEST_SCHEDULE: range(149, 164),
    AppendixType.FEE_SUMMARY: range(172, 187),
}

_HEADER_TEXTS = {
    "aligarh muslim university guide to admissions 2026-27",
    "aligarh muslim university",
    "guide to admissions 2026-27",
}
_SERIAL_RE = re.compile(r"^(\d+)\.?$")
_CONTENTS_ENTRY_RE = re.compile(
    r"^(?P<title>.+?)\s+(?P<start>\d{1,3})(?:\s*[–-]\s*(?P<end>\d{1,3}))?$"
)
_TABLE_LABEL_RE = re.compile(r"\s*\(Table[-\s]?[IVX]+\)\s*", re.IGNORECASE)
_TABLE_NUMBER_RE = re.compile(r"TABLE\s*[IVX]+", re.IGNORECASE)
_MATCH_STOPWORDS = {
    "the", "of", "for", "and", "in", "to", "under", "by", "their", "with", "at", "after",
    "table", "list",
}
# Contents page ranges are approximate; a section may spill onto the next page.
_CONTENTS_PAGE_TOLERANCE = 1
_CODE_RE = re.compile(r"^[A-Z0-9-]{3,10}$")


@dataclass(frozen=True)
class _ContentsEntry:
    title: str
    start: int
    end: int
    aliases: tuple[str, ...]

    def covers(self, page: int) -> bool:
        return self.start <= page <= self.end + _CONTENTS_PAGE_TOLERANCE


@dataclass
class _AppendixContext:
    programme_group: str | None = None
    faculty: str | None = None
    carried: dict[str, AppendixCell] = field(default_factory=dict)
    last_record_index: int | None = None


class PolicyParser:
    """Parse non-course guide content without discarding its page provenance."""

    def __init__(self, *, max_chunk_words: int = 300) -> None:
        if max_chunk_words < 50:
            raise ValueError("max_chunk_words must be at least 50")
        self.max_chunk_words = max_chunk_words

    def parse(self, extracted: ExtractedDocument) -> PolicyCorpus:
        pages = sorted(extracted.pages, key=lambda item: item.physical_page)
        sections = self._parse_policy_sections(extracted.document.document_id, pages)
        appendix_rows = self._parse_appendices(extracted.document.document_id, pages)
        return PolicyCorpus(
            document=extracted.document,
            sections=sections,
            appendix_rows=appendix_rows,
        )

    def _parse_policy_sections(
        self,
        document_id: str,
        pages: list[ExtractedPage],
    ) -> list[SectionRecord]:
        records: list[SectionRecord] = []
        contents = self._parse_contents(pages)
        major_heading: str | None = "Admissions policies"
        current_heading = major_heading

        for page in pages:
            if not self._in_ranges(page.physical_page, POLICY_PAGE_RANGES):
                continue

            printed = self._printed_number(page.printed_page)
            covering = [
                entry for entry in contents if printed is not None and entry.covers(printed)
            ]
            if contents:
                if covering:
                    # Carry the section over from the previous page while the
                    # contents still covers it; otherwise use the latest section
                    # that has started by this page.
                    if not any(entry.title == major_heading for entry in covering):
                        started = [entry for entry in covering if entry.start <= printed]
                        major_heading = (started or covering)[-1].title
                else:
                    # Pages outside the contents (forms, disclaimer) take their
                    # section from their own first heading.
                    major_heading = None

            content: list[ExtractedTextLine] = []
            local_index = 0
            previous_heading: ExtractedTextLine | None = None
            for line in sorted(page.lines, key=lambda item: item.bounding_box.top):
                if self._is_noise(line, page) or _TABLE_NUMBER_RE.fullmatch(line.text.strip()):
                    continue
                continues_heading = (
                    previous_heading is not None
                    and not content
                    and line.bounding_box.top - previous_heading.bounding_box.bottom <= 35
                )
                if self._is_heading(line, allow_small=continues_heading):
                    heading_text = self._clean_text(line.text).rstrip(":")
                    wrapped = continues_heading
                    if wrapped:
                        current_heading = f"{current_heading} {heading_text}"
                    else:
                        if content:
                            records.extend(
                                self._section_records(
                                    document_id,
                                    page,
                                    current_heading,
                                    major_heading or current_heading,
                                    content,
                                    local_index,
                                )
                            )
                            local_index += len(self._split_lines(content))
                            content = []
                        current_heading = heading_text
                    previous_heading = line

                    entry = self._match_contents(current_heading, covering)
                    if entry is not None:
                        major_heading = entry.title
                    elif not contents and line.max_font_size is not None and (
                        line.max_font_size >= 13
                    ):
                        major_heading = current_heading
                    elif contents and not covering and (major_heading is None or wrapped):
                        major_heading = current_heading
                    continue
                previous_heading = None
                content.append(line)

            if content:
                page_records = self._section_records(
                    document_id,
                    page,
                    current_heading,
                    major_heading or current_heading,
                    content,
                    local_index,
                )
                records.extend(page_records)

        return records

    @classmethod
    def _parse_contents(cls, pages: list[ExtractedPage]) -> list[_ContentsEntry]:
        """Read top-level policy sections and their printed pages from CONTENTS."""

        for page in pages:
            lines = sorted(page.lines, key=lambda item: item.bounding_box.top)
            if not any(line.text.strip().upper() == "CONTENTS" for line in lines):
                continue
            entries: list[_ContentsEntry] = []
            for line in lines:
                text = cls._clean_text(line.text)
                if text.upper() == "UNDER-GRADUATE PROGRAMMES":
                    break
                if text.startswith("•") and entries:
                    last = entries[-1]
                    alias = text.lstrip("• ").strip()
                    entries[-1] = _ContentsEntry(
                        last.title, last.start, last.end, (*last.aliases, alias)
                    )
                    continue
                match = _CONTENTS_ENTRY_RE.match(text)
                if match is None:
                    continue
                title = _TABLE_LABEL_RE.sub(" ", match.group("title")).strip()
                start = int(match.group("start"))
                end = int(match.group("end") or start)
                entries.append(_ContentsEntry(title, start, end, (title,)))
            return entries
        return []

    @classmethod
    def _match_contents(
        cls,
        heading: str,
        entries: list[_ContentsEntry],
    ) -> _ContentsEntry | None:
        heading_words = cls._match_words(heading)
        if not heading_words:
            return None
        best: tuple[float, _ContentsEntry] | None = None
        for entry in entries:
            for alias in entry.aliases:
                alias_words = cls._match_words(alias)
                if not alias_words:
                    continue
                overlap = len(heading_words & alias_words) / min(
                    len(heading_words), len(alias_words)
                )
                if overlap >= 0.75 and (best is None or overlap > best[0]):
                    best = (overlap, entry)
        return best[1] if best else None

    @staticmethod
    def _match_words(text: str) -> set[str]:
        words = re.findall(r"[a-z]+", text.lower())
        # Compare five-letter stems so spelling variants in the guide still
        # match (e.g. "DEBATOR" in a heading vs "Debater" in the contents).
        return {word[:5] for word in words if len(word) > 1 and word not in _MATCH_STOPWORDS}

    @staticmethod
    def _printed_number(printed_page: str | None) -> int | None:
        if printed_page and printed_page.isdigit():
            return int(printed_page)
        return None

    def _section_records(
        self,
        document_id: str,
        page: ExtractedPage,
        heading: str,
        major_heading: str,
        lines: list[ExtractedTextLine],
        start_index: int,
    ) -> list[SectionRecord]:
        results: list[SectionRecord] = []
        for offset, chunk_lines in enumerate(self._split_lines(lines)):
            text = "\n".join(self._clean_text(line.text) for line in chunk_lines)
            source = SourceReference(
                document_id=document_id,
                physical_page=page.physical_page,
                printed_page=page.printed_page,
                section=heading,
                bounding_box=self._union_boxes(
                    [line.bounding_box for line in chunk_lines]
                ),
            )
            heading_path = [major_heading] if major_heading != heading else []
            results.append(
                SectionRecord(
                    record_id=self._section_record_id(
                        document_id,
                        page.physical_page,
                        heading,
                        start_index + offset,
                    ),
                    document_id=document_id,
                    heading=heading,
                    heading_path=heading_path,
                    text=text,
                    source=source,
                )
            )
        return results

    def _split_lines(
        self,
        lines: list[ExtractedTextLine],
    ) -> list[list[ExtractedTextLine]]:
        chunks: list[list[ExtractedTextLine]] = []
        current: list[ExtractedTextLine] = []
        word_count = 0
        for line in lines:
            words = len(line.text.split())
            if current and word_count + words > self.max_chunk_words:
                chunks.append(current)
                current = []
                word_count = 0
            current.append(line)
            word_count += words
        if current:
            chunks.append(current)
        return chunks

    def _parse_appendices(
        self,
        document_id: str,
        pages: list[ExtractedPage],
    ) -> list[AppendixRecord]:
        records: list[AppendixRecord] = []
        contexts = {appendix_type: _AppendixContext() for appendix_type in APPENDIX_PAGE_RANGES}

        for page in pages:
            appendix_type = self._appendix_type(page.physical_page)
            if appendix_type is None or not page.tables:
                continue
            main_table = max(page.tables, key=lambda item: len(item.rows))
            self._parse_appendix_table(
                document_id,
                page,
                appendix_type,
                main_table.rows,
                contexts[appendix_type],
                records,
            )
        return records

    def _parse_appendix_table(
        self,
        document_id: str,
        page: ExtractedPage,
        appendix_type: AppendixType,
        rows: list[list[str | None]],
        context: _AppendixContext,
        records: list[AppendixRecord],
    ) -> None:
        for row_index, row in enumerate(rows):
            cells = [self._clean_text(cell) for cell in row if cell and cell.strip()]
            if not cells:
                continue
            serial_match = _SERIAL_RE.match(cells[0])
            if serial_match:
                parsed = self._appendix_course_row(
                    document_id,
                    page,
                    appendix_type,
                    serial_match.group(1),
                    cells[1:],
                    row_index,
                    context,
                )
                if parsed is not None:
                    records.append(parsed)
                    context.last_record_index = len(records) - 1
                continue

            if self._is_appendix_header(cells):
                continue
            if self._is_programme_group(cells):
                context.programme_group = cells[0]
                context.faculty = None
                continue
            if self._is_context_heading(cells):
                context.faculty = cells[0]
                continue
            if appendix_type is AppendixType.TEST_SCHEDULE:
                self._attach_schedule_continuation(
                    document_id,
                    page,
                    cells,
                    context,
                    records,
                )

    def _appendix_course_row(
        self,
        document_id: str,
        page: ExtractedPage,
        appendix_type: AppendixType,
        serial: str,
        cells: list[str],
        row_index: int,
        context: _AppendixContext,
    ) -> AppendixRecord | None:
        if not cells:
            return None
        source = SourceReference(
            document_id=document_id,
            physical_page=page.physical_page,
            printed_page=page.printed_page,
            section=appendix_type.value,
        )

        if appendix_type is AppendixType.FEE_SUMMARY:
            if len(cells) < 2:
                return None
            values = {"fee_at_admission": self._cell(cells[-1], source)}
            course_name = " ".join(cells[:-1])
            course_code = None
            category = None
        else:
            course_name = self._clean_course_name(cells[0])
            course_code = cells[1] if len(cells) > 1 and _CODE_RE.match(cells[1]) else None
            tail = cells[2:] if course_code else cells[1:]
            if appendix_type is AppendixType.APPLICATION_SUMMARY:
                category = None
                values = self._application_values(tail, source, context)
            else:
                category, values = self._schedule_values(tail, source, context)

        slug = re.sub(r"[^a-z0-9]+", "-", course_name.lower()).strip("-")[:60]
        return AppendixRecord(
            record_id=(
                f"{document_id}:{appendix_type.value}:{page.physical_page}:"
                f"{row_index + 1}:{serial}:{slug}"
            ),
            document_id=document_id,
            appendix_type=appendix_type,
            serial_number=serial,
            course_name=course_name,
            course_code=course_code,
            category=category,
            programme_group=context.programme_group,
            faculty=context.faculty,
            values=values,
            source=source,
        )

    def _application_values(
        self,
        cells: list[str],
        source: SourceReference,
        context: _AppendixContext,
    ) -> dict[str, AppendixCell]:
        explicit: dict[str, AppendixCell] = {}
        if not cells:
            return self._inherit_cells(context.carried)

        if not cells[0].lower().startswith("rs."):
            explicit["application_form_details"] = self._cell(cells[0], source)
            if len(cells) > 1:
                explicit["form_handling_office"] = self._cell(cells[-1], source)
            context.carried = explicit.copy()
            return explicit

        explicit["processing_charges"] = self._cell(cells[0], source)
        details = cells[1:]
        if details and details[0].lower().startswith("will be notified"):
            explicit["application_form_details"] = self._cell(details[0], source)
            if len(details) > 1:
                explicit["form_handling_office"] = self._cell(details[-1], source)
        else:
            date_keys = (
                "form_opening_date",
                "closing_without_late_fee",
                "closing_with_late_fee",
            )
            for key, value in zip(date_keys, details[:3]):
                explicit[key] = self._cell(value, source)
            if len(details) > 3:
                explicit["form_handling_office"] = self._cell(details[-1], source)

        context.carried = explicit.copy()
        return explicit

    def _schedule_values(
        self,
        cells: list[str],
        source: SourceReference,
        context: _AppendixContext,
    ) -> tuple[str | None, dict[str, AppendixCell]]:
        category = None
        if cells and cells[0] in {"T", "D", "N"}:
            category = cells.pop(0)
        keys = ("date_or_method", "duration", "scheduled_start")
        explicit = {
            key: self._cell(value, source)
            for key, value in zip(keys, cells)
        }
        carried_category = context.carried.get("category")
        if category is None and carried_category is not None:
            category = carried_category.text
        if category is not None:
            explicit_category = self._cell(category, source)
            explicit_category.inherited = not cells and carried_category is not None
            explicit["category"] = explicit_category

        if any(key in explicit for key in keys):
            context.carried = explicit.copy()
            return category, {key: value for key, value in explicit.items() if key != "category"}

        inherited = self._inherit_cells(context.carried)
        inherited_category = inherited.pop("category", None)
        if category is None and inherited_category is not None:
            category = inherited_category.text
        return category, inherited

    def _attach_schedule_continuation(
        self,
        document_id: str,
        page: ExtractedPage,
        cells: list[str],
        context: _AppendixContext,
        records: list[AppendixRecord],
    ) -> None:
        if context.last_record_index is None or len(cells) > 3:
            return
        previous = records[context.last_record_index]
        if previous.appendix_type is not AppendixType.TEST_SCHEDULE:
            return
        source = SourceReference(
            document_id=document_id,
            physical_page=page.physical_page,
            printed_page=page.printed_page,
            section=AppendixType.TEST_SCHEDULE.value,
        )
        updates = dict(previous.values)
        for key, value in zip(("duration", "scheduled_start"), cells):
            if key in updates:
                updates[key] = updates[key].model_copy(
                    update={"text": f"{updates[key].text} | {value}"}
                )
            else:
                updates[key] = self._cell(value, source)
        records[context.last_record_index] = previous.model_copy(update={"values": updates})
        for key in ("duration", "scheduled_start"):
            if key in updates:
                context.carried[key] = updates[key]

    @staticmethod
    def _cell(text: str, source: SourceReference) -> AppendixCell:
        return AppendixCell(text=text, source=source)

    @staticmethod
    def _inherit_cells(cells: dict[str, AppendixCell]) -> dict[str, AppendixCell]:
        return {
            key: value.model_copy(update={"inherited": True})
            for key, value in cells.items()
        }

    @staticmethod
    def _is_appendix_header(cells: list[str]) -> bool:
        joined = " ".join(cells).lower()
        return any(
            marker in joined
            for marker in (
                "name of course",
                "course of study",
                "processing charges",
                "form opening date",
                "form closing date",
                "scheduled start",
                "fee payable at the",
                "without late fee",
                "rs.300.00",
            )
        ) or cells == ["Fee of"]

    @staticmethod
    def _is_programme_group(cells: list[str]) -> bool:
        return len(cells) == 1 and any(
            marker in cells[0].upper()
            for marker in ("PROGRAM", "PROGAM", "COURSES", "DIPLOMA", "CERTIFICATE")
        )

    @staticmethod
    def _is_context_heading(cells: list[str]) -> bool:
        if len(cells) != 1:
            return False
        text = cells[0]
        return (
            text.lower().startswith(("faculty of ", "centre for ", "center for "))
            or "college" in text.lower()
            or "school" in text.lower()
            or "academy" in text.lower()
            or "planning" in text.lower()
            or "polytechnic" in text.lower()
        )

    @staticmethod
    def _is_heading(line: ExtractedTextLine, *, allow_small: bool = False) -> bool:
        text = line.text.strip()
        if len(text) > 140 or re.match(r"^(?:\d+\.|[•\-])\s", text):
            return False
        if line.max_font_size is not None and line.max_font_size >= 13:
            return True
        # Real guide headings are bold; unbolded lines ending in ":" or set in
        # capitals are sentence fragments, form text or addresses.
        if not any("bold" in font.lower() for font in line.font_names):
            return False
        if re.match(r"^Note\b", text, re.IGNORECASE):
            return False
        # Small bold text is usually a table header; accept it only as the
        # continuation of a heading directly above it.
        if not allow_small and line.max_font_size is not None and line.max_font_size < 11:
            return False
        letters = [character for character in text if character.isalpha()]
        is_upper = bool(letters) and all(character.isupper() for character in letters)
        return (is_upper and len(text) >= 5) or (
            text.endswith(":")
            and len(text) <= 90
            and not text.lower().startswith(("http", "www"))
        )

    @staticmethod
    def _is_noise(line: ExtractedTextLine, page: ExtractedPage) -> bool:
        text = line.text.strip()
        lowered = text.lower()
        if lowered in _HEADER_TEXTS:
            return True
        if line.bounding_box.top >= page.height * 0.94 and re.fullmatch(
            r"(?:[A-K]\.)?\d+", text, re.IGNORECASE
        ):
            return True
        return False

    @staticmethod
    def _union_boxes(boxes: list[BoundingBox]) -> BoundingBox:
        return BoundingBox(
            x0=min(box.x0 for box in boxes),
            top=min(box.top for box in boxes),
            x1=max(box.x1 for box in boxes),
            bottom=max(box.bottom for box in boxes),
        )

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _clean_course_name(cls, value: str) -> str:
        text = cls._clean_text(value)
        return re.sub(r"^([A-Z])\s+([a-z])", r"\1\2", text)

    @staticmethod
    def _in_ranges(page: int, ranges: tuple[range, ...]) -> bool:
        return any(page in page_range for page_range in ranges)

    @staticmethod
    def _appendix_type(page: int) -> AppendixType | None:
        return next(
            (
                appendix_type
                for appendix_type, page_range in APPENDIX_PAGE_RANGES.items()
                if page in page_range
            ),
            None,
        )

    @staticmethod
    def _section_record_id(
        document_id: str,
        page: int,
        heading: str,
        index: int,
    ) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:64]
        return f"{document_id}:policy:{page}:{index + 1}:{slug}"
