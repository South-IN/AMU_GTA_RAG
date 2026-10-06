"""AMU admissions retrieval pipeline."""

from .config import AppPaths
from .models import (
    BoundingBox,
    CourseField,
    CourseCorpus,
    CourseRecord,
    CourseTable,
    CourseTableCell,
    DocumentRecord,
    ExtractedDocument,
    ExtractedPage,
    ExtractedTable,
    ExtractedTextLine,
    ProgramLevel,
    ReviewMetadata,
    ReviewStatus,
    SectionRecord,
    SourceReference,
)

__all__ = [
    "AppPaths",
    "BoundingBox",
    "CourseField",
    "CourseCorpus",
    "CourseRecord",
    "CourseTable",
    "CourseTableCell",
    "DocumentRecord",
    "ExtractedDocument",
    "ExtractedPage",
    "ExtractedTable",
    "ExtractedTextLine",
    "ProgramLevel",
    "ReviewMetadata",
    "ReviewStatus",
    "SectionRecord",
    "SourceReference",
]
__version__ = "0.1.0"
