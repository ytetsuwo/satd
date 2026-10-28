#!/usr/bin/env python3
"""Compare the legacy Eclipse tool output with the Maldonado dataset.

``data/legacy_tool_comments.csv`` is exported from the legacy tool's
PostgreSQL ``processed_comment`` table.  It has no full file path, so the
path is reconstructed from ``classname`` and ``filename``:
``<package>/<filename>``.  The dataset-file subset keeps comments whose
reconstructed path is one of the files in
``data/comment_locations_all.csv``.
"""
import argparse
import csv
import os
from collections import Counter, defaultdict


def normalize(text: str) -> str:
    return " ".join(text.split())


def repo_path(row: dict) -> str:
    filename = row["filename"]
    simple = filename[:-5] if filename.endswith(".java") else filename
    segments = row["classname"].split(".")
    index = None
    for i, segment in enumerate(segments):
        if segment == simple:
            index = i
            break
    package = ".".join(segments[:index]) if index is not None else ""
    return (package.replace(".", "/") + "/" if package else "") + filename


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comments", default="data/legacy_tool_comments.csv")
    parser.add_argument("--locations", default="data/comment_locations_all.csv")
    parser.add_argument("--dataset", default="maldonado_corrected.csv")
    parser.add_argument("--output", default="data/legacy_tool_counts.csv")
    args = parser.parse_args()

    files = defaultdict(set)
    basenames = defaultdict(list)
    with open(args.locations, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("match_status") != "matched":
                continue
            project = row["project_name"]
            path = row.get("file_path", "").replace("\\", "/")
            if path and path not in files[project]:
                files[project].add(path)
                basenames[(project, os.path.basename(path))].append(path)

    dataset_counts = Counter()
    dataset_texts = defaultdict(set)
    with open(args.dataset, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            project = row["project_name"]
            dataset_counts[project] += 1
            dataset_texts[project].add(normalize(row["comment_text"]))

    all_counts = Counter()
    filtered_counts = Counter()
    all_texts = defaultdict(set)
    filtered_texts = defaultdict(set)
    with open(args.comments, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            project = row["projectname"]
            text = normalize(row["commenttext"])
            all_counts[project] += 1
            all_texts[project].add(text)

            relative = repo_path(row)
            candidates = basenames.get((project, row["filename"]), [])
            if any(path == relative or path.endswith("/" + relative) for path in candidates):
                filtered_counts[project] += 1
                filtered_texts[project].add(text)

    rows = []
    for project in sorted(dataset_counts):
        expected = dataset_counts[project]
        all_count = all_counts[project]
        filtered_count = filtered_counts[project]
        unique_dataset = dataset_texts[project]
        unique_all = all_texts[project]
        unique_filtered = filtered_texts[project]
        common = len(unique_filtered & unique_dataset)
        rows.append(
            {
                "project_name": project,
                "all_files": all_count,
                "dataset_files": filtered_count,
                "dataset": expected,
                "diff_all_pct": 100.0 * (all_count - expected) / expected,
                "diff_dataset_files_pct": 100.0 * (filtered_count - expected) / expected,
                "unique_all": len(unique_all),
                "unique_dataset_files": len(unique_filtered),
                "unique_dataset": len(unique_dataset),
                "recall_dataset_files_pct": 100.0 * common / len(unique_dataset) if unique_dataset else 0.0,
                "precision_dataset_files_pct": 100.0 * common / len(unique_filtered) if unique_filtered else 0.0,
            }
        )

    total_all = sum(all_counts.values())
    total_filtered = sum(filtered_counts.values())
    total_dataset = sum(dataset_counts.values())
    unique_all = set().union(*all_texts.values())
    unique_filtered = set().union(*filtered_texts.values())
    unique_dataset = set().union(*dataset_texts.values())
    common = len(unique_filtered & unique_dataset)
    rows.append(
        {
            "project_name": "TOTAL",
            "all_files": total_all,
            "dataset_files": total_filtered,
            "dataset": total_dataset,
            "diff_all_pct": 100.0 * (total_all - total_dataset) / total_dataset,
            "diff_dataset_files_pct": 100.0 * (total_filtered - total_dataset) / total_dataset,
            "unique_all": len(unique_all),
            "unique_dataset_files": len(unique_filtered),
            "unique_dataset": len(unique_dataset),
            "recall_dataset_files_pct": 100.0 * common / len(unique_dataset),
            "precision_dataset_files_pct": 100.0 * common / len(unique_filtered),
        }
    )

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'project':32} {'all':>7} {'dataset files':>13} {'dataset':>8} {'diff all':>9} {'diff files':>10}")
    for row in rows:
        print(
            f"{row['project_name']:32} {row['all_files']:7d} {row['dataset_files']:13d} "
            f"{row['dataset']:8d} {row['diff_all_pct']:+8.2f}% {row['diff_dataset_files_pct']:+9.2f}%"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
