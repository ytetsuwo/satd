#!/usr/bin/env python3

import argparse
import csv
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read a CSV file and print a compact summary."
    )
    parser.add_argument("csv_path", help="Path to the input CSV file")
    parser.add_argument(
        "--delimiter",
        default=",",
        help="CSV delimiter (default: ,)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8)",
    )
    parser.add_argument(
        "--group-by",
        action="append",
        default=[],
        help="Column to aggregate. Can be specified multiple times.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of values to show per group (default: 10)",
    )
    return parser.parse_args()


def choose_default_groups(fieldnames: list[str]) -> list[str]:
    defaults = []
    for candidate in ("classification", "project_name"):
        if candidate in fieldnames:
            defaults.append(candidate)
    return defaults


def load_rows(csv_path: Path, delimiter: str, encoding: str) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("The CSV file does not contain a header row.")
        return reader.fieldnames, list(reader)


def count_missing(rows: list[dict[str, str]], fieldnames: list[str]) -> dict[str, int]:
    missing = {field: 0 for field in fieldnames}
    for row in rows:
        for field in fieldnames:
            value = row.get(field)
            if value is None or value.strip() == "":
                missing[field] += 1
    return missing


def format_group_counts(rows: list[dict[str, str]], group_by: list[str], top: int) -> list[str]:
    lines: list[str] = []
    for column in group_by:
        counter = Counter()
        for row in rows:
            value = (row.get(column) or "").strip() or "<empty>"
            counter[value] += 1

        lines.append(f"\nTop values for '{column}':")
        for value, count in counter.most_common(top):
            lines.append(f"  {value}: {count}")
    return lines


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    fieldnames, rows = load_rows(csv_path, args.delimiter, args.encoding)
    group_by = args.group_by or choose_default_groups(fieldnames)
    invalid_columns = [column for column in group_by if column not in fieldnames]
    if invalid_columns:
        raise ValueError(
            "Unknown group-by column(s): " + ", ".join(invalid_columns)
        )

    missing = count_missing(rows, fieldnames)

    print(f"File: {csv_path}")
    print(f"Rows: {len(rows)}")
    print(f"Columns: {len(fieldnames)}")
    print("Header: " + ", ".join(fieldnames))
    print("\nMissing values by column:")
    for field in fieldnames:
        print(f"  {field}: {missing[field]}")

    if group_by:
        for line in format_group_counts(rows, group_by, args.top):
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
