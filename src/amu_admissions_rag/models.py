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


class AppendixType(str, Enum):
    APPLICATION_SUMMARY = "application_summary"
    TEST_SCHEDULE = "test_schedule"
    FEE_SUMMARY = "fee_summary"


class ChunkType(str, Enum):
    COURSE_OVERVIEW = "course_overview"
    COURSE_FIELD = "course_field"
    COURSE_TABLE_ROW = "course_table_row"
    POLICY_SECTION = "policy_section"
    APPENDIX_ROW = "appendix_row"


class QueryIntent(str, Enum):
    ELIGIBILITY = "eligibility"
    AGE_LIMIT = "age_limit"
    SELECTION_PROCESS = "selection_process"
    TEST_DETAILS = "test_details"
    TEST_CENTRES = "test_centres"
    INTAKE = "intake"
    DURATION = "duration"
    FEES = "fees"
    APPLICATION_DATES = "application_dates"
    TEST_SCHEDULE = "test_schedule"
    GENERAL = "general"


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


class ReviewDecision(BaseModel):
    record_id: NonEmptyText
    status: ReviewStatus
    notes: str | None = None

    @model_validator(mode="after")
    def reject_pending_decision(self) -> "ReviewDecision":
        if self.status is ReviewStatus.PENDING:
            raise ValueError("review decisions must approve or reject a record")
        return self


class ReviewBatch(BaseModel):
    reviewer: NonEmptyText
    reviewed_at: datetime
    decisions: list[ReviewDecision] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_record_ids(self) -> "ReviewBatch":
        record_ids = [decision.record_id for decision in self.decisions]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("review decisions contain duplicate record IDs")
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


class AppendixCell(BaseModel):
    text: NonEmptyText
    inherited: bool = False
    source: SourceReference


class AppendixRecord(BaseModel):
    record_id: NonEmptyText
    document_id: NonEmptyText
    appendix_type: AppendixType
    serial_number: NonEmptyText
    course_name: NonEmptyText
    source: SourceReference
    course_code: str | None = None
    category: str | None = None
    programme_group: str | None = None
    faculty: str | None = None
    values: dict[str, AppendixCell] = Field(default_factory=dict)
    review: ReviewMetadata = Field(default_factory=ReviewMetadata)


class ExtractedTextLine(BaseModel):
    text: NonEmptyText
    bounding_box: BoundingBox
    font_names: list[str] = Field(default_factory=list)
    max_font_size: float | None = None


class ExtractedTable(BaseModel):
    table_index: int = Field(ge=1)
    bounding_box: BoundingBox
    rows: list[list[str | None]]


class ExtractedPage(BaseModel):
    physical_page: int = Field(ge=1)
    printed_page: str | None = None
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    text: str
    lines: list[ExtractedTextLine]
    tables: list[ExtractedTable]


class ExtractedDocument(BaseModel):
    document: DocumentRecord
    pages: list[ExtractedPage]


class CourseCorpus(BaseModel):
    document: DocumentRecord
    courses: list[CourseRecord]


class PolicyCorpus(BaseModel):
    document: DocumentRecord
    sections: list[SectionRecord]
    appendix_rows: list[AppendixRecord]


class RetrievalChunk(BaseModel):
    chunk_id: NonEmptyText
    document_id: NonEmptyText
    chunk_type: ChunkType
    parent_record_id: NonEmptyText
    title: NonEmptyText
    text: NonEmptyText
    source: SourceReference
    field_name: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    review: ReviewMetadata


class IndexCorpus(BaseModel):
    document: DocumentRecord
    chunks: list[RetrievalChunk]


class CourseAliasMatch(BaseModel):
    abbreviation: NonEmptyText
    full_name: NonEmptyText
    matched_text: NonEmptyText
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_span(self) -> "CourseAliasMatch":
        if self.end <= self.start:
            raise ValueError("alias match end must be greater than start")
        return self


class QueryAnalysis(BaseModel):
    original_query: NonEmptyText
    expanded_query: NonEmptyText
    aliases: list[CourseAliasMatch] = Field(default_factory=list)
    intents: list[QueryIntent] = Field(default_factory=list)
    preferred_fields: list[str] = Field(default_factory=list)


class RetrievalHit(BaseModel):
    chunk: RetrievalChunk
    fused_score: float = Field(ge=0)
    lexical_score: float = Field(ge=0)
    vector_score: float
    lexical_rank: int | None = Field(default=None, ge=1)
    vector_rank: int | None = Field(default=None, ge=1)
    intent_boost: float = Field(default=0, ge=0)
    exact_value_boost: float = Field(default=0, ge=0)
    course_match_boost: float = Field(default=0, ge=0)


class RetrievalResponse(BaseModel):
    query: QueryAnalysis
    hits: list[RetrievalHit] = Field(default_factory=list)
    course_parents: dict[str, CourseRecord] = Field(default_factory=dict)
    embedding_provider: NonEmptyText


class CourseCandidate(BaseModel):
    course: CourseRecord
    score: float = Field(ge=0)
    program_level_boost: float = Field(default=0, ge=0)
    profile: RetrievalHit
    evidence: list[RetrievalHit] = Field(default_factory=list)


class CourseDiscoveryResponse(BaseModel):
    query: QueryAnalysis
    candidates: list[CourseCandidate] = Field(default_factory=list)
    embedding_provider: NonEmptyText
