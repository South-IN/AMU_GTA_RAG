"""AMU admissions retrieval pipeline."""

from .config import AppPaths
from .models import (
    BoundingBox,
    CourseField,
    CourseRecord,
    CourseTable,
    CourseTableCell,
    DocumentRecord,
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
    "CourseRecord",
    "CourseTable",
    "CourseTableCell",
    "DocumentRecord",
    "ProgramLevel",
    "ReviewMetadata",
    "ReviewStatus",
    "SectionRecord",
    "SourceReference",
]
__version__ = "0.1.0"

