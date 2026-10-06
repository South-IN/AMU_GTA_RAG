"""Project paths and source-document configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_PDF_NAME = "c7cabd0dcdcb3d7793446b0ea7c88a49.pdf"


@dataclass(frozen=True)
class AppPaths:
    """Filesystem locations used by the ingestion pipeline."""

    project_root: Path

    @classmethod
    def from_package(cls) -> "AppPaths":
        return cls(project_root=Path(__file__).resolve().parents[2])

    @property
    def source_pdf(self) -> Path:
        return self.project_root / DEFAULT_PDF_NAME

    @property
    def processed_dir(self) -> Path:
        return self.project_root / "data" / "processed"

    @property
    def review_dir(self) -> Path:
        return self.project_root / "data" / "review"

    def ensure_output_directories(self) -> None:
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.review_dir.mkdir(parents=True, exist_ok=True)

