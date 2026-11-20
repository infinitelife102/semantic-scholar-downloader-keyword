#!/usr/bin/env python3
"""
Download open-access papers on raising hydro and thermal power output.

Each search runs from 2026 back to 2010. PDFs and JSON metadata are
stored under the output path by publication date:

    OUTPUT/hydro/turbine-efficiency/202403/15/0001_Hydro_PAPERID.pdf
    OUTPUT/hydro/turbine-efficiency/202403/15/0001_Hydro_PAPERID.json

Set OUTPUT_DIR below, or pass --output. --output wins when both are set.

    python download_papers.py --output "E:\\Research\\PowerPapers"
    python download_papers.py --output "E:\\Research\\PowerPapers" --per-query 2
"""

import argparse
import subprocess
import sys
from pathlib import Path


# 저장 위치. 원하는 폴더를 적으면 그 안에 논문이 저장됩니다.
# 비워 두면 이 스크립트 옆의 papers 폴더를 사용합니다.
# 실행할 때 --output 을 주면 그 경로가 이 값보다 우선합니다.
#
# 예: OUTPUT_DIR = r"E:\Research\PowerPapers"
OUTPUT_DIR = r"D:\20260929_PowerPapers"


# Twelve searches, 420 successful PDFs each, about 5,000 papers.
SEARCHES = [
    (
        "hydro",
        "turbine-efficiency",
        "hydropower turbine efficiency improvement",
    ),
    (
        "hydro",
        "francis",
        "Francis turbine performance upgrade",
    ),
    (
        "hydro",
        "kaplan",
        "Kaplan turbine efficiency optimization",
    ),
    (
        "hydro",
        "pumped-storage",
        "pumped storage hydropower efficiency",
    ),
    (
        "hydro",
        "generator",
        "hydroelectric generator capacity uprating",
    ),
    (
        "hydro",
        "small-hydro",
        "small hydropower output optimization",
    ),
    (
        "thermal",
        "plant-efficiency",
        "thermal power plant efficiency improvement",
    ),
    (
        "thermal",
        "steam-turbine",
        "steam turbine heat rate improvement",
    ),
    (
        "thermal",
        "coal",
        "coal fired power plant efficiency upgrade",
    ),
    (
        "thermal",
        "ccgt",
        "combined cycle gas turbine efficiency",
    ),
    (
        "thermal",
        "boiler",
        "boiler efficiency improvement thermal power",
    ),
    (
        "thermal",
        "supercritical",
        "supercritical power plant efficiency",
    ),
]


def main():

    script_dir = Path(__file__).resolve().parent
    downloader = script_dir / "downloader.py"

    parser = argparse.ArgumentParser(
        description=(
            "Download hydro and thermal power papers "
            "into publication-date folders."
        )
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Root folder for the downloads. "
            "Overrides OUTPUT_DIR at the top of this file. "
            "Default: OUTPUT_DIR, or papers next to this script."
        ),
    )

    parser.add_argument(
        "--per-query",
        type=int,
        default=420,
        help=(
            "Successful PDFs to download for each search. "
            "Default: 420 (12 searches, about 5,000 papers)."
        ),
    )

    parser.add_argument(
        "--year-from",
        type=int,
        default=2010,
        help="Earliest publication year. Default: 2010.",
    )

    parser.add_argument(
        "--year-to",
        type=int,
        default=2026,
        help=(
            "Latest publication year. "
            "Search starts here and moves backward. "
            "Default: 2026."
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between PDF downloads. Default: 2.",
    )

    parser.add_argument(
        "--search-delay",
        type=float,
        default=3.0,
        help="Seconds between search pages. Default: 3.",
    )

    args = parser.parse_args()

    if args.per_query <= 0:
        parser.error(
            "--per-query must be greater than 0"
        )

    if args.year_from > args.year_to:
        parser.error(
            "--year-from cannot be later than --year-to"
        )

    if not downloader.is_file():
        parser.error(
            f"Cannot find {downloader}"
        )

    if args.output:
        chosen_output = args.output
    elif OUTPUT_DIR.strip():
        chosen_output = OUTPUT_DIR
    else:
        chosen_output = script_dir / "papers"

    output_root = Path(chosen_output).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Hydro and thermal power paper download")
    print("=" * 70)
    print(f"Output:     {output_root}")
    print(f"Searches:   {len(SEARCHES)}")
    print(f"Per search: {args.per_query} PDFs")
    print(
        f"Years:      {args.year_to} down to {args.year_from}"
    )
    print("=" * 70)

    failed = []

    for index, (group, name, query) in enumerate(SEARCHES, start=1):

        output_dir = output_root / group / name
        prefix = "Hydro" if group == "hydro" else "Thermal"

        print()
        print("=" * 70)
        print(f"[{index}/{len(SEARCHES)}] {group}/{name}")
        print(f"Query:  {query}")
        print(f"Folder: {output_dir}")
        print("=" * 70)

        command = [
            sys.executable,
            str(downloader),
            "--query",
            query,
            "--max-results",
            str(args.per_query),
            "--output",
            str(output_dir),
            "--prefix",
            prefix,
            "--year-from",
            str(args.year_from),
            "--year-to",
            str(args.year_to),
            "--delay",
            str(args.delay),
            "--search-delay",
            str(args.search_delay),
        ]

        completed = subprocess.run(command)

        if completed.returncode != 0:
            failed.append(f"{group}/{name}")
            print()
            print(
                f"Search failed: {group}/{name} "
                f"(exit {completed.returncode})"
            )

    print()
    print("=" * 70)
    print("ALL SEARCHES FINISHED")
    print(f"Output: {output_root}")

    if failed:
        print("Failed searches:")
        for name in failed:
            print(f"  {name}")
        print("=" * 70)
        return 1

    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
