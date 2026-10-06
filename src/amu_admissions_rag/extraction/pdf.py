"""Layout-aware extraction for the admissions guide."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from amu_admissions_rag.models import (
    BoundingBox,
    DocumentRecord,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
    ExtractedTextLine,
)


PRINTED_PAGE_PATTERNS = (
    re.compile(r"^[A-K]\.\d+$", re.IGNORECASE),
    re.compile(r"^\d+$"),
    re.compile(r"^\([ivxlcdm]+\)$", re.IGNORECASE),
)


def parse_page_spec(value: str, total_pages: int | None = None) -> list[int]:
    """Parse selections such as 1,54-56,128 into sorted physical page numbers."""

    pages: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", maxsplit=1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"invalid descending page range: {token}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(token))

    if not pages:
        raise ValueError("at least one page must be selected")
    if min(pages) < 1:
        raise ValueError("page numbers start at 1")
    if total_pages is not None and max(pages) > total_pages:
        raise ValueError(f"page selection exceeds document length of {total_pages}")
    return sorted(pages)


class PdfExtractor:
    """Extract document metadata, positioned text and tables from a PDF."""

    def __init__(
        self,
        pdf_path: Path,
        document_id: str = "amu-guide-2026-27",
        academic_year: str = "2026-27",
    ) -> None:
        self.pdf_path = Path(pdf_path)
        self.document_id = document_id
        self.academic_year = academic_year
        if not self.pdf_path.is_file():
            raise FileNotFoundError(self.pdf_path)

    def document_record(self) -> DocumentRecord:
        reader = PdfReader(self.pdf_path)
        return DocumentRecord(
            document_id=self.document_id,
            filename=self.pdf_path.name,
            academic_year=self.academic_year,
            sha256=self._sha256(),
            total_pages=len(reader.pages),
        )

    def extract_pages(
        self,
        page_numbers: Iterable[int],
        *,
        include_tables: bool = True,
    ) -> ExtractedDocument:
        document = self.document_record()
        selected = sorted(set(page_numbers))
        if not selected:
            raise ValueError("at least one page must be selected")
        if selected[0] < 1 or selected[-1] > document.total_pages:
            raise ValueError("page selection is outside the document")

        extracted_pages: list[ExtractedPage] = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_number in selected:
                page = pdf.pages[page_number - 1]
                extracted_pages.append(
                    self._extract_page(page, page_number, include_tables=include_tables)
                )

        return ExtractedDocument(document=document, pages=extracted_pages)

    def _extract_page(
        self,
        page: pdfplumber.page.Page,
        page_number: int,
        *,
        include_tables: bool,
    ) -> ExtractedPage:
        text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
        lines = self._extract_lines(page)
        tables = self._extract_tables(page) if include_tables else []
        return ExtractedPage(
            physical_page=page_number,
            printed_page=self._infer_printed_page(lines),
            width=float(page.width),
            height=float(page.height),
            text=text,
            lines=lines,
            tables=tables,
        )

    def _extract_lines(self, page: pdfplumber.page.Page) -> list[ExtractedTextLine]:
        words = page.extract_words(
            x_tolerance=2,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False,
            extra_attrs=["fontname", "size"],
        )
        words.sort(key=lambda item: (round(float(item["top"]), 1), float(item["x0"])))

        grouped: list[list[dict[str, object]]] = []
        for word in words:
            if not grouped:
                grouped.append([word])
                continue
            current_top = float(grouped[-1][0]["top"])
            if abs(float(word["top"]) - current_top) <= 2.0:
                grouped[-1].append(word)
            else:
                grouped.append([word])

        lines: list[ExtractedTextLine] = []
        for group in grouped:
            ordered = sorted(group, key=lambda item: float(item["x0"]))
            text = " ".join(str(item["text"]) for item in ordered).strip()
            if not text:
                continue
            font_names = sorted(
                {str(item["fontname"]) for item in ordered if item.get("fontname")}
            )
            sizes = [float(item["size"]) for item in ordered if item.get("size") is not None]
            lines.append(
                ExtractedTextLine(
                    text=text,
                    bounding_box=BoundingBox(
                        x0=min(float(item["x0"]) for item in ordered),
                        top=min(float(item["top"]) for item in ordered),
                        x1=max(float(item["x1"]) for item in ordered),
                        bottom=max(float(item["bottom"]) for item in ordered),
                    ),
                    font_names=font_names,
                    max_font_size=max(sizes) if sizes else None,
                )
            )
        return lines

    def _extract_tables(self, page: pdfplumber.page.Page) -> list[ExtractedTable]:
        extracted: list[ExtractedTable] = []
        for index, table in enumerate(page.find_tables(), start=1):
            x0, top, x1, bottom = table.bbox
            rows = [[self._clean_cell(cell) for cell in row] for row in table.extract()]
            extracted.append(
                ExtractedTable(
                    table_index=index,
                    bounding_box=BoundingBox(
                        x0=float(x0),
                        top=float(top),
                        x1=float(x1),
                        bottom=float(bottom),
                    ),
                    rows=rows,
                )
            )
        return extracted

    def _infer_printed_page(self, lines: list[ExtractedTextLine]) -> str | None:
        for line in reversed(lines[-12:]):
            candidate = line.text.strip()
            for pattern in PRINTED_PAGE_PATTERNS:
                if pattern.fullmatch(candidate):
                    return candidate.strip("()")
        return None

    @staticmethod
    def _clean_cell(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cleaned or None

    def _sha256(self) -> str:
        digest = hashlib.sha256()
        with self.pdf_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

