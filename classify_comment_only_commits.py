#!/usr/bin/env python3
"""Classify comment-only commits by what happened to their SATD comments.

For each commit classified as comment_only, compare the blamed SATD comment
ranges with the commit diff and decide whether the SATD comment was added,
deleted, rewritten, kept (moved/reformatted), or untouched.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from classify_satd_commits import commit_diff, commit_metadata

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def normalize(text: str) -> str:
    return " ".join(text.split())


@dataclass
class LineChange:
    line_number: int
    text: str


@dataclass
class FileDiff:
    added: list[LineChange] = field(default_factory=list)
    removed: list[LineChange] = field(default_factory=list)


def parse_diff(diff: str) -> dict[str, FileDiff]:
    files: dict[str, FileDiff] = defaultdict(FileDiff)
    path = ""
    old_line = new_line = 0
    in_hunk = False

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            path = ""
            continue
        if line.startswith("+++ "):
            value = line[4:].strip()
            if value != "/dev/null":
                path = value[2:] if value.startswith("b/") else value
                files[path]
            continue
        match = HUNK_RE.match(line)
        if match:
            old_line, new_line = int(match.group(1)), int(match.group(2))
            in_hunk = True
            continue
        if not in_hunk or not path:
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("+"):
            files[path].added.append(LineChange(new_line, line[1:]))
            new_line += 1
        elif line.startswith("-"):
            files[path].removed.append(LineChange(old_line, line[1:]))
            old_line += 1
        elif line.startswith(" "):
            old_line += 1
            new_line += 1
    return dict(files)


def is_comment_text(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith(("//", "/*", "*", "<!--", "--"))


def load_links(path: Path) -> dict[tuple[str, str], list[dict[str, str]]]:
    links: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["satd"] != "1" or row["match_status"] != "matched":
                continue
            for commit_id in row["blame_commit_ids"].split(";"):
                if not commit_id:
                    continue
                links[(row["project_name"], commit_id)].append(row)
    return links


def classify_location(
    location: dict[str, str],
    files: dict[str, FileDiff],
) -> str:
    start = int(location["start_line"])
    end = int(location["end_line"])
    file_diff = files.get(location["file_path"])
    if file_diff is None:
        return "untouched"

    removed_hit = any(start <= change.line_number <= end for change in file_diff.removed)
    text = normalize(location["comment_text"])
    added_same = any(
        text and text in normalize(change.text) for change in file_diff.added
    )
    added_comment = any(is_comment_text(change.text) for change in file_diff.added)

    if removed_hit:
        if added_same:
            return "kept"
        if added_comment:
            return "rewritten"
        return "deleted"
    if added_same:
        return "added"
    return "untouched"


def summarize_category(statuses: list[str]) -> str:
    unique = set(statuses)
    if not unique or unique == {"untouched"}:
        return "other_comments"
    if len(unique) == 1:
        status = next(iter(unique))
        return f"satd_{status}"
    return "mixed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify comment-only commits by their SATD comment changes."
    )
    parser.add_argument(
        "--locations",
        type=Path,
        default=Path("data/comment_locations_all.csv"),
        help="Comment location CSV (default: data/comment_locations_all.csv)",
    )
    parser.add_argument(
        "--classification",
        type=Path,
        default=Path("data/satd_commit_classification.csv"),
        help="Commit classification CSV (default: data/satd_commit_classification.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/comment_only_commit_changes.csv"),
        help="Output CSV (default: data/comment_only_commit_changes.csv)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    links = load_links(args.locations)

    with args.classification.open("r", encoding="utf-8", newline="") as handle:
        commits = [
            row
            for row in csv.DictReader(handle)
            if row["classification"] == "comment_only"
        ]

    rows = []
    for commit in commits:
        project = commit["project_name"]
        commit_id = commit["commit_id"]
        locations = links.get((project, commit_id), [])
        repo = Path(locations[0]["repo_path"]) if locations else None
        files = parse_diff(commit_diff(repo, commit_id)) if repo else {}
        statuses = [classify_location(location, files) for location in locations]
        counts = Counter(statuses)
        rows.append(
            {
                "project_name": project,
                "commit_id": commit_id,
                "author_name": commit["author_name"],
                "commit_date": commit["commit_date"],
                "subject": commit["subject"],
                "satd_comments": str(len(locations)),
                "added": str(counts["added"]),
                "deleted": str(counts["deleted"]),
                "rewritten": str(counts["rewritten"]),
                "kept": str(counts["kept"]),
                "untouched": str(counts["untouched"]),
                "category": summarize_category(statuses),
            }
        )

    rows.sort(key=lambda row: (row["project_name"], row["commit_id"]))
    fieldnames = list(rows[0].keys())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"comment-only commits: {len(rows)}")
    for category, count in sorted(Counter(row["category"] for row in rows).items()):
        links = sum(int(row["satd_comments"]) for row in rows if row["category"] == category)
        print(f"{category:<16} commits {count:>3} SATD comments {links:>4}")
    print()
    for project in sorted({row["project_name"] for row in rows}):
        subset = [row for row in rows if row["project_name"] == project]
        counts = Counter(row["category"] for row in subset)
        print(f"{project:<32} commits {len(subset):>3} {dict(counts)}")
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
