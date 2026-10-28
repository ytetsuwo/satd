#!/usr/bin/env python3
"""Compare JdtExtract output with the Maldonado dataset.

The extractor writes a per-file stage report (``<out>.csv``) and a comment
list (``<out>.csv.comments.csv``).  This script aggregates both by project
and reports comment counts and unique-text overlap against
``maldonado_corrected.csv``.
"""
import argparse
import base64
import csv
from collections import Counter, defaultdict


def normalize(text: str) -> str:
    return " ".join(text.split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="jdt_out.csv")
    parser.add_argument("--comments", default="jdt_out.csv.comments.csv")
    parser.add_argument("--dataset", default="maldonado_corrected.csv")
    parser.add_argument("--output", default="data/jdt_extractor_counts.csv")
    args = parser.parse_args()

    tool_counts = Counter()
    with open(args.report, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tool_counts[row["project"]] += int(row["final"])

    tool_texts = defaultdict(set)
    with open(args.comments, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            text = base64.b64decode(row["text_b64"]).decode("utf-8", "replace")
            tool_texts[row["project"]].add(normalize(text))

    dataset_counts = Counter()
    dataset_texts = defaultdict(set)
    with open(args.dataset, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            project = row["project_name"]
            dataset_counts[project] += 1
            dataset_texts[project].add(normalize(row["comment_text"]))

    rows = []
    for project in sorted(dataset_counts):
        extracted = tool_counts[project]
        expected = dataset_counts[project]
        unique_tool = tool_texts[project]
        unique_dataset = dataset_texts[project]
        common = len(unique_tool & unique_dataset)
        rows.append(
            {
                "project_name": project,
                "extracted": extracted,
                "dataset": expected,
                "diff": extracted - expected,
                "diff_pct": 100.0 * (extracted - expected) / expected,
                "unique_extracted": len(unique_tool),
                "unique_dataset": len(unique_dataset),
                "recall_pct": 100.0 * common / len(unique_dataset) if unique_dataset else 0.0,
                "precision_pct": 100.0 * common / len(unique_tool) if unique_tool else 0.0,
            }
        )

    total_tool = sum(tool_counts.values())
    total_dataset = sum(dataset_counts.values())
    all_tool = set().union(*tool_texts.values())
    all_dataset = set().union(*dataset_texts.values())
    common = len(all_tool & all_dataset)
    rows.append(
        {
            "project_name": "TOTAL",
            "extracted": total_tool,
            "dataset": total_dataset,
            "diff": total_tool - total_dataset,
            "diff_pct": 100.0 * (total_tool - total_dataset) / total_dataset,
            "unique_extracted": len(all_tool),
            "unique_dataset": len(all_dataset),
            "recall_pct": 100.0 * common / len(all_dataset),
            "precision_pct": 100.0 * common / len(all_tool),
        }
    )

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"{'project':32} {'extracted':>9} {'dataset':>8} {'diff':>7} "
        f"{'pct':>8} {'recall':>8} {'precision':>9}"
    )
    for row in rows:
        print(
            f"{row['project_name']:32} {row['extracted']:9d} {row['dataset']:8d} "
            f"{row['diff']:+7d} {row['diff_pct']:+7.2f}% "
            f"{row['recall_pct']:7.2f}% {row['precision_pct']:8.2f}%"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
