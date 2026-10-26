#!/usr/bin/env python3
"""Classify SATD-related commits as comment-only or code-changing.

For every commit that git blame attributes to a SATD comment, inspect the
commit diff and decide whether it changed source code or only comments.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class FileChanges:
    old_path: str
    added: list[tuple[int, str]]
    removed: list[tuple[int, str]]


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        errors="replace",
    )


def code_line_flags(text: str) -> list[bool]:
    """Return True for each line that contains code outside comments/strings."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    flags = [False] * (normalized.count("\n") + 1)
    index = 0
    line = 0
    block_end = ""
    quote = ""
    length = len(normalized)

    while index < length:
        char = normalized[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if block_end:
            if normalized.startswith(block_end, index):
                index += len(block_end)
                block_end = ""
            else:
                index += 1
            continue
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if normalized.startswith("//", index):
            newline = normalized.find("\n", index)
            index = length if newline < 0 else newline
            continue
        if normalized.startswith("/*", index):
            block_end = "*/"
            index += 2
            continue
        if normalized.startswith("<!--", index):
            block_end = "-->"
            index += 4
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if not char.isspace():
            flags[line] = True
        index += 1

    return flags


def file_content(repo: Path, revision: str, path: str) -> str | None:
    completed = run_git(repo, ["show", f"{revision}:{path}"])
    if completed.returncode != 0:
        return None
    return completed.stdout


def parse_diff(diff: str) -> dict[str, FileChanges]:
    files: dict[str, FileChanges] = {}
    new_path = ""
    old_path = ""
    old_line = 0
    new_line = 0
    in_hunk = False
    current_key = ""

    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            in_hunk = False
            continue
        if raw.startswith("--- "):
            old_path = clean_diff_path(raw[4:])
            continue
        if raw.startswith("+++ "):
            new_path = clean_diff_path(raw[4:])
            current_key = new_path or old_path
            files.setdefault(current_key, FileChanges(old_path, [], []))
            continue
        match = HUNK_RE.match(raw)
        if match:
            old_line = int(match.group(1))
            new_line = int(match.group(3))
            in_hunk = True
            continue
        if not in_hunk or not raw:
            continue
        marker = raw[0]
        if marker == "+":
            files[current_key].added.append((new_line, raw[1:]))
            new_line += 1
        elif marker == "-":
            files[current_key].removed.append((old_line, raw[1:]))
            old_line += 1
        elif marker == " ":
            old_line += 1
            new_line += 1

    return files


def clean_diff_path(value: str) -> str:
    value = value.rstrip("\t")
    if value == "/dev/null":
        return ""
    if value.startswith(("a/", "b/")):
        return value[2:]
    return value


def count_changed_lines(
    repo: Path,
    revision: str,
    path: str,
    lines: list[tuple[int, str]],
) -> tuple[int, int]:
    if not lines:
        return 0, 0
    content = file_content(repo, revision, path)
    if content is None:
        return 0, 0
    flags = code_line_flags(content)

    comment_count = 0
    code_count = 0
    for line_number, text in lines:
        if not text.strip():
            continue
        if line_number < 1 or line_number > len(flags):
            code_count += 1
            continue
        if flags[line_number - 1]:
            code_count += 1
        else:
            comment_count += 1
    return comment_count, code_count


def commit_metadata(repo: Path, sha: str) -> tuple[str, str, str, str]:
    completed = run_git(repo, ["show", "-s", "--format=%an%x09%ae%x09%aI%x09%s", sha])
    if completed.returncode != 0:
        return "", "", "", ""
    parts = completed.stdout.rstrip("\n").split("\t", 3)
    while len(parts) < 4:
        parts.append("")
    return tuple(parts)  # type: ignore[return-value]


def commit_diff(repo: Path, sha: str) -> str:
    completed = run_git(
        repo,
        ["show", "--format=", "--no-color", "--unified=0", "--no-renames", "--root", sha],
    )
    if completed.returncode == 0 and completed.stdout.strip():
        return completed.stdout
    merge = run_git(
        repo,
        ["diff-tree", "-m", "-p", "--root", "--unified=0", "--no-renames", sha],
    )
    return merge.stdout if merge.returncode == 0 else ""


def load_satd_commits(path: Path) -> tuple[dict[str, Path], Counter[tuple[str, str]]]:
    project_repos: dict[str, Path] = {}
    commits: Counter[tuple[str, str]] = Counter()

    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("satd") != "1" or row.get("match_status") != "matched":
                continue
            project = row["project_name"]
            project_repos.setdefault(project, Path(row["repo_path"]))
            for sha in filter(None, row.get("blame_commit_ids", "").split(";")):
                commits[(project, sha)] += 1
    return project_repos, commits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split SATD commits into comment-only and code changes."
    )
    parser.add_argument(
        "--locations",
        type=Path,
        default=Path("data/comment_locations_all.csv"),
        help="Output of find_comment_locations.py with blame columns",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/satd_commit_classification.csv"),
        help="Classification CSV path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_repos, commits = load_satd_commits(args.locations)

    rows = []
    for (project, sha), occurrences in sorted(commits.items()):
        repo = project_repos[project]
        author, email, date, subject = commit_metadata(repo, sha)
        diff = commit_diff(repo, sha)

        comment_lines = 0
        code_lines = 0
        changed_files = 0
        for path, changes in parse_diff(diff).items():
            if not changes.added and not changes.removed:
                continue
            changed_files += 1
            added_comments, added_code = count_changed_lines(
                repo, sha, path, changes.added
            )
            removed_comments, removed_code = count_changed_lines(
                repo, f"{sha}^", changes.old_path or path, changes.removed
            )
            comment_lines += added_comments + removed_comments
            code_lines += added_code + removed_code

        if comment_lines == 0 and code_lines == 0:
            classification = "no_changes"
        elif code_lines == 0:
            classification = "comment_only"
        else:
            classification = "code"

        rows.append(
            {
                "project_name": project,
                "commit_id": sha,
                "author_name": author,
                "author_email": email,
                "commit_date": date,
                "subject": subject,
                "satd_comments": str(occurrences),
                "changed_files": str(changed_files),
                "comment_lines": str(comment_lines),
                "code_lines": str(code_lines),
                "classification": classification,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "project_name",
        "commit_id",
        "author_name",
        "author_email",
        "commit_date",
        "subject",
        "satd_comments",
        "changed_files",
        "comment_lines",
        "code_lines",
        "classification",
    ]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["classification"] for row in rows)
    print(f"commits: {len(rows)}")
    for name in ("comment_only", "code", "no_changes"):
        print(f"  {name}: {counts.get(name, 0)}")
    for name in ("comment_only", "code", "no_changes"):
        comments = sum(
            int(row["satd_comments"]) for row in rows if row["classification"] == name
        )
        print(f"  SATD links in {name}: {comments}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
