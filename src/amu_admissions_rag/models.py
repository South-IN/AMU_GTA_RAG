"""Validated records shared by extraction, review and retrieval."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator


NonEmptyText = Annotated[str, Field(min_length=1)]


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProgramLevel(str, Enum):
    UNDERGRADUATE = "undergraduate"
    POSTGRADUATE = "postgraduate"
    RESEARCH = "research"
    DIPLOMA = "diploma"
    SCHOOL = "school"
    BRIDGE = "bridge"
    CERTIFICATE = "certificate"
    OTHER = "other"


class BoundingBox(BaseModel):
    x0: float = Field(ge=0)
    top: float = Field(ge=0)
    x1: float = Field(ge=0)
    bottom: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "BoundingBox":
        if self.x1 < self.x0:
            raise ValueError("x1 must be greater than or equal to x0")
        if self.bottom < self.top:
            raise ValueError("bottom must be greater than or equal to top")
        return self


class SourceReference(BaseModel):
    document_id: NonEmptyText
    physical_page: int = Field(ge=1)
    printed_page: str | None = None
    section: str | None = None
    bounding_box: BoundingBox | None = None


class ReviewMetadata(BaseModel):
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_completed_review(self) -> "ReviewMetadata":
        if self.status is not ReviewStatus.PENDING:
            if not self.reviewer or not self.reviewed_at:
                raise ValueError("completed reviews require reviewer and reviewed_at")
        return self


class DocumentRecord(BaseModel):
    document_id: NonEmptyText
    filename: NonEmptyText
    academic_year: NonEmptyText
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    total_pages: int = Field(ge=1)


class CourseField(BaseModel):
    name: NonEmptyText
    label: NonEmptyText
    value: NonEmptyText
    source: SourceReference


class CourseTableCell(BaseModel):
    text: str
    inherited: bool = False
    source: SourceReference | None = None


class CourseTable(BaseModel):
    name: NonEmptyText
    headers: list[NonEmptyText]
    rows: list[dict[str, CourseTableCell]]
    source: SourceReference


class CourseRecord(BaseModel):
    record_id: NonEmptyText
    document_id: NonEmptyText
    course_name: NonEmptyText
    program_level: ProgramLevel
    faculty: NonEmptyText
    source: SourceReference
    course_code: str | None = None
    campus: str | None = None
    fields: list[CourseField] = Field(default_factory=list)
    tables: list[CourseTable] = Field(default_factory=list)
    review: ReviewMetadata = Field(default_factory=ReviewMetadata)


class SectionRecord(BaseModel):
    record_id: NonEmptyText
    document_id: NonEmptyText
    heading: NonEmptyText
    heading_path: list[NonEmptyText] = Field(default_factory=list)
    text: NonEmptyText
    source: SourceReference
    review: ReviewMetadata = Field(default_factory=ReviewMetadata)

