"""Run the complete ingestion pipeline and load the approved corpus."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.corpus import DATABASE_URL_ENV
from amu_admissions_rag.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract the guide, parse pending records, apply human-review batches, "
            "build the approved index and load it into PostgreSQL"
        )
    )
    parser.add_argument(
        "--reviews-dir",
        type=Path,
        help="Directory of review-batch JSON files (default: reviews/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild and reload even if the inputs are unchanged since the last load",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Replace a populated database corpus even when nothing is approved",
    )
    parser.add_argument(
        "--no-database",
        action="store_true",
        help=f"Write local JSON artifacts only, even if {DATABASE_URL_ENV} is set",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = AppPaths.from_package()
    database_url = None if args.no_database else os.environ.get(DATABASE_URL_ENV) or None
    run_pipeline(
        paths=paths,
        database_url=database_url,
        reviews_dir=args.reviews_dir or paths.project_root / "reviews",
        force=args.force,
        allow_empty=args.allow_empty,
    )


if __name__ == "__main__":
    main()
