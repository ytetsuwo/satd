#!/usr/bin/env python3
"""Validate and summarize SATD commit classifications."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_commit(value: str) -> str:
    return value.strip()


def commit_key(row: dict[str, str]) -> tuple[str, str]:
    return (row["project_name"], normalize_commit(row["commit_id"]))


def load_links(rows: list[dict[str, str]]) -> list[tuple[str, str, str, str]]:
    links: list[tuple[str, str, str, str]] = []
    for row in rows:
        if row.get("satd") != "1" or row.get("match_status") != "matched":
            continue
        for commit in row["blame_commit_ids"].split(";"):
            commit = normalize_commit(commit)
            if commit:
                links.append(
                    (
                        row["project_name"],
                        commit,
                        row["classification"],
                        row["comment_text"],
                    )
                )
    return links


def pct(part: int, total: int) -> str:
    return f"{part / total:.1%}" if total else "-"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and summarize SATD commit classifications."
    )
    parser.add_argument(
        "--locations",
        type=Path,
        default=Path("data/comment_locations_all.csv"),
    )
    parser.add_argument(
        "--classification",
        type=Path,
        default=Path("data/satd_commit_classification.csv"),
    )
    parser.add_argument(
        "--recheck",
        type=Path,
        help="Optional second classification CSV to compare against.",
    )
    args = parser.parse_args()

    locations = read_csv(args.locations)
    commits = read_csv(args.classification)
    links = load_links(locations)

    commit_rows = {commit_key(row): row for row in commits}
    errors: list[str] = []

    if len(commit_rows) != len(commits):
        errors.append(f"duplicate commit rows: {len(commits) - len(commit_rows)}")

    link_counts = Counter((project, commit) for project, commit, _, _ in links)
    for key, count in link_counts.items():
        row = commit_rows.get(key)
        if row is None:
            errors.append(f"linked commit missing from classification: {key}")
            continue
        if int(row["satd_comments"]) != count:
            errors.append(
                f"satd_comments mismatch: {key} csv={row['satd_comments']} links={count}"
            )
    for key, row in commit_rows.items():
        if int(row["satd_comments"]) == 0:
            errors.append(f"commit without links: {key}")

    total_links = sum(int(row["satd_comments"]) for row in commits)
    if total_links != len(links):
        errors.append(f"total links: classification={total_links} locations={len(links)}")

    for key, row in commit_rows.items():
        comment_lines = int(row["comment_lines"])
        code_lines = int(row["code_lines"])
        changed_files = int(row["changed_files"])
        classification = row["classification"]
        if changed_files == 0:
            errors.append(f"commit without changed files: {key}")
        if classification == "comment_only":
            if code_lines != 0 or comment_lines == 0:
                errors.append(f"bad comment_only counts: {key}")
        elif classification == "code":
            if code_lines == 0:
                errors.append(f"code commit without code lines: {key}")
        elif classification == "no_changes":
            if comment_lines or code_lines:
                errors.append(f"no_changes commit has lines: {key}")
        else:
            errors.append(f"unknown classification: {key} {classification}")

    recheck_diffs = 0
    if args.recheck:
        recheck_rows = read_csv(args.recheck)
        recheck = {commit_key(row): row for row in recheck_rows}
        fields = list(commits[0].keys())
        for key in sorted(set(commit_rows) | set(recheck)):
            left = commit_rows.get(key)
            right = recheck.get(key)
            if left is None or right is None:
                recheck_diffs += 1
                continue
            for field in fields:
                if left.get(field) != right.get(field):
                    recheck_diffs += 1
                    break
    if recheck_diffs:
        errors.append(f"recheck differences: {recheck_diffs}")

    print(f"commits: {len(commits)}")
    print(f"SATD links: {len(links)}")
    print(f"recheck differences: {recheck_diffs}")
    print(f"validation errors: {len(errors)}")
    for error in errors[:20]:
        print(f"  {error}")
    print()

    class_counts = Counter(row["classification"] for row in commits)
    link_class_counts = Counter(
        commit_rows[(project, commit)]["classification"]
        for project, commit, _, _ in links
        if (project, commit) in commit_rows
    )
    print("## classification")
    print("| classification | commits | share | links | share |")
    print("|---|---:|---:|---:|---:|")
    for name in ("comment_only", "code", "no_changes"):
        print(
            f"| {name} | {class_counts[name]} | {pct(class_counts[name], len(commits))} "
            f"| {link_class_counts[name]} | {pct(link_class_counts[name], len(links))} |"
        )
    print()

    by_project: dict[str, Counter[str]] = defaultdict(Counter)
    links_by_project: dict[str, Counter[str]] = defaultdict(Counter)
    for row in commits:
        project = row["project_name"]
        by_project[project]["commits"] += 1
        by_project[project][row["classification"]] += 1
        by_project[project]["comment_lines"] += int(row["comment_lines"])
        by_project[project]["code_lines"] += int(row["code_lines"])
    for project, commit, _, _ in links:
        row = commit_rows.get((project, commit))
        if row is not None:
            links_by_project[project][row["classification"]] += 1
            links_by_project[project]["links"] += 1

    print("## project")
    print("| project | commits | comment_only | code | links | comment_only links |")
    print("|---|---:|---:|---:|---:|---:|")
    for project in sorted(by_project):
        stats = by_project[project]
        link_stats = links_by_project[project]
        print(
            f"| {project} | {stats['commits']} | {stats['comment_only']} | {stats['code']} "
            f"| {link_stats['links']} | {link_stats['comment_only']} |"
        )
    print()

    by_kind: dict[str, Counter[str]] = defaultdict(Counter)
    for project, commit, kind, _ in links:
        row = commit_rows.get((project, commit))
        if row is None:
            continue
        by_kind[kind or "UNKNOWN"][row["classification"]] += 1
        by_kind[kind or "UNKNOWN"]["links"] += 1
    print("## SATD classification")
    print("| SATD classification | links | comment_only | code |")
    print("|---|---:|---:|---:|")
    for kind in sorted(by_kind):
        stats = by_kind[kind]
        print(
            f"| {kind} | {stats['links']} | {stats['comment_only']} | {stats['code']} |"
        )
    print()

    by_year: dict[str, Counter[str]] = defaultdict(Counter)
    for row in commits:
        year = row["commit_date"][:4]
        by_year[year]["commits"] += 1
        by_year[year][row["classification"]] += 1
    print("## year")
    print("| year | commits | comment_only | code |")
    print("|---|---:|---:|---:|")
    for year in sorted(by_year):
        stats = by_year[year]
        print(f"| {year} | {stats['commits']} | {stats['comment_only']} | {stats['code']} |")
    print()

    authors = Counter()
    author_comment_only = Counter()
    for row in commits:
        author = row["author_name"]
        authors[author] += 1
        if row["classification"] == "comment_only":
            author_comment_only[author] += 1
    print("## top authors by comment_only commits")
    print("| author | comment_only | commits |")
    print("|---|---:|---:|")
    for author, count in author_comment_only.most_common(10):
        print(f"| {author} | {count} | {authors[author]} |")
    print()

    print("## top commits by SATD links")
    print("| project | commit | links | classification | subject |")
    print("|---|---|---:|---|---|")
    for row in sorted(commits, key=lambda item: -int(item["satd_comments"]))[:10]:
        subject = row["subject"].replace("|", " ")
        print(
            f"| {row['project_name']} | {row['commit_id'][:10]} | {row['satd_comments']} "
            f"| {row['classification']} | {subject} |"
        )

    print()
    print("PASS" if not errors else "FAIL")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
