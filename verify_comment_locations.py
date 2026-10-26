#!/usr/bin/env python3
"""Verify locations produced by find_comment_locations.py.

For every matched row, check that the comment text occurs in the reported
file and line range.  Also check the structural consistency of the output:
row count, input row correspondence, status fields, and blame metadata.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


def normalize(text: str) -> str:
    return " ".join(text.split())


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def comment_fragments(text: str) -> list[str]:
    parts = re.split(r"//|/\*+|\*+/|\*+", text)
    return [compact(part) for part in parts if re.sub(r"\W", "", part)]


def fragments_in_order(text: str, segment: str) -> bool:
    position = 0
    for fragment in comment_fragments(text):
        index = segment.find(fragment, position)
        if index < 0:
            return False
        position = index + len(fragment)
    return True


@dataclass
class ProjectStats:
    total: int = 0
    matched: int = 0
    not_found: int = 0
    repo_not_found: int = 0
    other_status: int = 0
    exact: int = 0
    contains: int = 0
    fragments: int = 0
    text_mismatch: int = 0
    blame_blamed: int = 0
    blame_other: int = 0
    blame_cr_only: int = 0
    blame_field_errors: int = 0
    structural_errors: int = 0
    examples: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify find_comment_locations.py output against the dataset."
    )
    parser.add_argument("output", help="Output CSV produced by find_comment_locations.py")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("maldonado_corrected.csv"),
        help="Input dataset used for the run (default: maldonado_corrected.csv)",
    )
    parser.add_argument(
        "--repos-root",
        type=Path,
        default=Path("repos"),
        help="Directory containing the repositories (default: repos)",
    )
    parser.add_argument(
        "--max-text-failure-rate",
        type=float,
        default=0.01,
        help="Allowed fraction of matched rows whose text is not found (default: 0.01)",
    )
    parser.add_argument(
        "--examples",
        type=int,
        default=10,
        help="Number of failure examples to print (default: 10)",
    )
    parser.add_argument(
        "--partial",
        action="store_true",
        help="Do not require every dataset row to appear in the output",
    )
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def load_lines(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").split("\n")
    except OSError:
        return None


def main() -> int:
    args = parse_args()

    fieldnames, rows = read_csv(Path(args.output))
    _, dataset = read_csv(args.dataset)

    required = {
        "project_name",
        "comment_text",
        "match_status",
        "repo_path",
        "file_path",
        "start_line",
        "end_line",
        "blame_status",
    }
    missing = required.difference(fieldnames)
    if missing:
        print(f"ERROR: missing column(s): {', '.join(sorted(missing))}")
        return 2

    if len(rows) != len(dataset):
        print(f"NOTE: output rows {len(rows)} != dataset rows {len(dataset)}")

    stats: dict[str, ProjectStats] = defaultdict(ProjectStats)
    file_cache: dict[Path, list[str] | None] = {}
    cr_only_cache: dict[Path, bool] = {}
    row_number_errors = 0
    dataset_by_row = {number: row for number, row in enumerate(dataset, start=2)}
    covered_rows: set[int] = set()

    for index, row in enumerate(rows):
        project = row["project_name"]
        project_stats = stats[project]
        project_stats.total += 1

        if "input_row" in fieldnames and row["input_row"]:
            input_row = int(row["input_row"])
            covered_rows.add(input_row)
            expected = dataset_by_row.get(input_row)
        else:
            expected = dataset[index] if index < len(dataset) else None
        if expected is None:
            row_number_errors += 1
        elif (
            project != expected["project_name"]
            or row["comment_text"] != expected["comment_text"]
        ):
            row_number_errors += 1

        status = row["match_status"]
        if status == "repo_not_found":
            project_stats.repo_not_found += 1
            if row["repo_path"] or row["file_path"]:
                project_stats.structural_errors += 1
            continue
        if status == "not_found":
            project_stats.not_found += 1
            if not row["repo_path"] or row["file_path"]:
                project_stats.structural_errors += 1
            continue
        if status != "matched":
            project_stats.other_status += 1
            continue

        project_stats.matched += 1
        if not row["repo_path"] or not row["file_path"]:
            project_stats.structural_errors += 1
            continue

        try:
            start = int(row["start_line"])
            end = int(row["end_line"])
        except ValueError:
            project_stats.structural_errors += 1
            continue

        path = Path(row["repo_path"]) / row["file_path"]
        if path not in file_cache:
            file_cache[path] = load_lines(path)
        lines = file_cache[path]
        if lines is None or start < 1 or end < start or end > len(lines):
            project_stats.structural_errors += 1
            continue

        segment = compact(" ".join(lines[start - 1:end]))
        text = compact(row["comment_text"])
        if segment == text:
            project_stats.exact += 1
        elif text in segment:
            project_stats.contains += 1
        elif fragments_in_order(row["comment_text"], segment):
            project_stats.fragments += 1
        else:
            project_stats.text_mismatch += 1
            if len(project_stats.examples) < args.examples:
                project_stats.examples.append(
                    f"{project}:{row['file_path']}:{start}-{end} "
                    f"{text[:70]!r} not in {segment[:70]!r}"
                )

        blame_status = row["blame_status"]
        if blame_status == "blamed":
            project_stats.blame_blamed += 1
            if not row["blame_commit_ids"] or not row["blame_line_commits"]:
                project_stats.blame_field_errors += 1
        elif path not in cr_only_cache:
            body = path.read_bytes()
            cr_only_cache[path] = b"\n" not in body and b"\r" in body
            if cr_only_cache[path]:
                project_stats.blame_cr_only += 1
            else:
                project_stats.blame_other += 1
        elif cr_only_cache[path]:
            project_stats.blame_cr_only += 1
        else:
            project_stats.blame_other += 1

    total = sum(project_stats.total for project_stats in stats.values())
    matched = sum(project_stats.matched for project_stats in stats.values())
    text_mismatch = sum(project_stats.text_mismatch for project_stats in stats.values())
    structural = sum(project_stats.structural_errors for project_stats in stats.values())
    blame_other = sum(project_stats.blame_other for project_stats in stats.values())
    blame_cr_only = sum(
        project_stats.blame_cr_only for project_stats in stats.values()
    )
    blame_field_errors = sum(
        project_stats.blame_field_errors for project_stats in stats.values()
    )
    missing_rows = 0 if args.partial else len(dataset_by_row) - len(covered_rows)

    print(f"rows: {total} (dataset {len(dataset)})")
    if "input_row" in fieldnames and not args.partial:
        print(f"dataset rows not in output: {missing_rows}")
    print(
        "status: "
        + ", ".join(
            f"{name} {count}"
            for name, count in sorted(
                Counter(row["match_status"] for row in rows).items()
            )
        )
    )
    print(f"input row / dataset differences: {row_number_errors}")
    print()
    print(
        f"{'project':<32} {'rows':>6} {'matched':>8} {'not_found':>9} "
        f"{'no_repo':>8} {'text_ng':>8} {'blame_ng':>9}"
    )
    for project in sorted(stats):
        project_stats = stats[project]
        print(
            f"{project:<32} {project_stats.total:>6} {project_stats.matched:>8} "
            f"{project_stats.not_found:>9} {project_stats.repo_not_found:>8} "
            f"{project_stats.text_mismatch:>8} "
            f"{project_stats.blame_other + project_stats.blame_field_errors:>9}"
        )
    print()

    exact = sum(project_stats.exact for project_stats in stats.values())
    contains = sum(project_stats.contains for project_stats in stats.values())
    fragments = sum(project_stats.fragments for project_stats in stats.values())
    print(
        f"text: exact {exact}, contained {contains}, fragments {fragments}, "
        f"mismatch {text_mismatch} ({text_mismatch / matched:.4%} of matched)"
    )
    print(
        f"blame: blamed {matched - blame_other - blame_cr_only}, other {blame_other}, "
        f"cr-only files {blame_cr_only}, field errors {blame_field_errors}"
    )

    for project in sorted(stats):
        for example in stats[project].examples:
            print(f"  text mismatch: {example}")

    text_rate = text_mismatch / matched if matched else 0.0
    failed = (
        row_number_errors > 0
        or missing_rows > 0
        or structural > 0
        or blame_other > 0
        or blame_field_errors > 0
        or text_rate > args.max_text_failure_rate
    )
    print()
    print("FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
