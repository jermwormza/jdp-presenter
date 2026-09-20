#!/usr/bin/env python3
"""Build the distributable starter library from the configured local libraries."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.persistence.library_package import STARTER_PACKAGE_NAME, export_library


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / STARTER_PACKAGE_NAME,
        help="Destination .jdplibrary file",
    )
    args = parser.parse_args()
    summary = export_library(args.output)
    print(
        f"Built {args.output} with {summary.songs} song(s) "
        f"and {summary.bibles} Bible(s)."
    )


if __name__ == "__main__":
    main()
