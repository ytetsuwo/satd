#!/usr/bin/env python3
"""Check that find_comment_locations.py reproduces the msr16 locations.

The ground truth is data/msr16_td_removal/satd_locations.csv, which covers
apache-ant, apache-jmeter, and jruby. Every ground-truth (file_path,
comment_start_line) must appear among the tool's matches for the same comment.

Usage:
    python3 check_msr16.py

The repositories must already be checked out under repos/ (see setup_repos.sh).
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# msr16 project name -> project_name in maldonado_corrected.csv
PROJECTS = {
    "apache-ant": "apache-ant-1.7.0",
    "apache-jmeter": "apache-jmeter-2.10",
    "jruby": "jruby-1.4.0",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_ground_truth(path: Path) -> dict[tuple[str, str], set[tuple[str, int]]]:
    buckets: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            project = PROJECTS[row["project_name"]]
            key = (project, normalize(row["comment_text"]))
            buckets[key].add(
                (row["file_path"].lstrip("./"), int(row["comment_start_line"]))
            )
    return buckets


def run_tool(
    tool: Path,
    dataset: Path,
    mapping: Path,
    output_dir: Path,
    max_matches: int,
) -> dict[tuple[str, str], set[tuple[str, int]]]:
    buckets: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    for project in PROJECTS.values():
        output = output_dir / f"{project}.csv"
        command = [
            sys.executable,
            str(tool),
            str(dataset),
            "--mapping",
            str(mapping),
            "--project",
            project,
            "--mode",
            "unique",
            "--max-matches",
            str(max_matches),
            "--output",
            str(output),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        with output.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["match_status"] != "matched":
                    continue
                key = (row["project_name"], normalize(row["comment_text"]))
                buckets[key].add(
                    (row["file_path"].lstrip("./"), int(row["start_line"]))
                )
    return buckets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", type=Path, default=ROOT / "find_comment_locations.py")
    parser.add_argument("--dataset", type=Path, default=ROOT / "maldonado_corrected.csv")
    parser.add_argument("--mapping", type=Path, default=ROOT / "repo_map.csv")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=ROOT / "data/msr16_td_removal/satd_locations.csv",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=1000,
        help="Maximum matches per comment (default: 1000).",
    )
    args = parser.parse_args()

    for path in (args.tool, args.dataset, args.mapping, args.ground_truth):
        if not path.exists():
            print(f"error: not found: {path}", file=sys.stderr)
            return 2

    ground_truth = load_ground_truth(args.ground_truth)
    expected = sum(len(locations) for locations in ground_truth.values())
    print(f"ground truth: {len(ground_truth)} comments, {expected} locations")

    with tempfile.TemporaryDirectory(prefix="check_msr16_") as tmp:
        actual = run_tool(
            args.tool, args.dataset, args.mapping, Path(tmp), args.max_matches
        )

    missing_buckets = 0
    missing_locations: list[tuple[str, str, str, int]] = []
    for (project, comment), locations in ground_truth.items():
        found = actual.get((project, comment))
        if found is None:
            missing_buckets += 1
            continue
        for file_path, line in sorted(locations - found):
            missing_locations.append((project, comment, file_path, line))

    extra = sum(
        len(locations - ground_truth[key])
        for key, locations in actual.items()
        if key in ground_truth
    )

    for project in PROJECTS.values():
        keys = [key for key in ground_truth if key[0] == project]
        expected_count = sum(len(ground_truth[key]) for key in keys)
        missing = sum(
            1
            for key in keys
            for location in ground_truth[key] - actual.get(key, set())
        )
        status = "OK" if missing == 0 and all(key in actual for key in keys) else "NG"
        print(f"  {project}: {expected_count - missing}/{expected_count} {status}")

    if missing_buckets:
        print(f"comments not found at all: {missing_buckets}")
    for project, comment, file_path, line in missing_locations:
        print(f"missing: {project} {file_path}:{line} ({comment[:60]!r})")
    print(f"missing locations: {len(missing_locations)}")
    print(f"extra tool locations: {extra}")

    if missing_locations or missing_buckets:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
