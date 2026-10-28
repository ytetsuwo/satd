#!/usr/bin/env python3
"""Build the JdtExtract input list from the located dataset comments.

Only files that have at least one matched dataset comment are kept.  The
output is a two-column CSV (project, repo-relative path) without a header
repetition; JdtExtract skips the first line of the file.
"""
import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--locations",
        default="data/comment_locations_all.csv",
        help="comment location CSV produced by find_comment_locations.py",
    )
    parser.add_argument("--output", default="jdt_files.csv")
    args = parser.parse_args()

    files = set()
    with open(args.locations, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("match_status") != "matched":
                continue
            project = row.get("project_name", "")
            path = row.get("file_path", "")
            if project and path and path.endswith(".java"):
                files.add((project, path.replace("\\", "/")))

    output = Path(args.output)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["project", "file"])
        for project, path in sorted(files):
            writer.writerow([project, path])

    print(f"wrote {len(files)} files to {output}")


if __name__ == "__main__":
    main()
