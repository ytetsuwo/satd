#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re


WHITESPACE_RE = re.compile(r"\s+")
FLATTENED_SPLIT_RE = re.compile(
    r"\s+(?=(?://|/\*{1,2}|\*/|<!--|-->|\*(?:\s|/)|#|;|--\s))"
)
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "node_modules",
    "build",
    "dist",
    "target",
    "out",
    "bin",
}
TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".gradle",
    ".groovy",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".jsp",
    ".kt",
    ".kts",
    ".md",
    ".php",
    ".pl",
    ".properties",
    ".py",
    ".rb",
    ".scala",
    ".sql",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
COMMENT_PREFIXES = ("<!--", "-->", "//", "/*", "*/", "--", "#", "*", ";")


@dataclass(frozen=True)
class CommentBlock:
    text: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class MatchLocation:
    file_path: str
    start_line: int
    end_line: int
    match_type: str


def flat_key(lines: list[str]) -> str:
    return " ".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Locate comment_text entries inside source repositories."
    )
    parser.add_argument("csv_path", help="Input CSV path")
    parser.add_argument(
        "--repos-root",
        type=Path,
        help="Directory that contains repositories named after project_name",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        help="CSV file with columns: project_name,repo_path",
    )
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help="Only process the specified project_name. Can be used multiple times.",
    )
    parser.add_argument(
        "--mode",
        choices=("unique", "rows"),
        default="unique",
        help="Output one row per unique comment or per input CSV row.",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=5,
        help="Maximum number of matched locations to emit per comment.",
    )
    parser.add_argument(
        "--output",
        default="comment_locations.csv",
        help="Output CSV path. Use - for stdout.",
    )
    return parser.parse_args()


def load_input_rows(csv_path: Path, projects: set[str]) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("The input CSV does not contain a header row.")
        required = {"project_name", "comment_text"}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise ValueError(
                "The input CSV is missing required column(s): "
                + ", ".join(sorted(missing))
            )

        rows: list[dict[str, str]] = []
        for row_number, row in enumerate(reader, start=2):
            if projects and row["project_name"] not in projects:
                continue
            copied = dict(row)
            copied["_row_number"] = str(row_number)
            rows.append(copied)
        return reader.fieldnames, rows


def load_mapping(mapping_path: Path | None) -> dict[str, Path]:
    if mapping_path is None:
        return {}

    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or {"project_name", "repo_path"}.difference(reader.fieldnames):
            raise ValueError("The mapping CSV must contain project_name and repo_path columns.")

        mapping: dict[str, Path] = {}
        for row in reader:
            project_name = (row.get("project_name") or "").strip()
            repo_path = (row.get("repo_path") or "").strip()
            if project_name and repo_path:
                mapping[project_name] = Path(repo_path).expanduser()
        return mapping


def resolve_repo_path(
    project_name: str,
    repos_root: Path | None,
    mapping: dict[str, Path],
) -> Path | None:
    mapped = mapping.get(project_name)
    if mapped and mapped.exists():
        return mapped

    if repos_root is not None:
        candidate = repos_root / project_name
        if candidate.exists():
            return candidate

    return None


def should_scan_file(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    try:
        return path.stat().st_size <= 2_000_000
    except OSError:
        return False


def iter_source_files(repo_path: Path):
    for path in repo_path.rglob("*"):
        if path.is_dir() and path.name in IGNORED_DIRS:
            continue
        if path.is_file() and should_scan_file(path):
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            yield path


def normalize_line(line: str, strip_prefix: bool) -> str:
    collapsed = WHITESPACE_RE.sub(" ", line.strip())
    if not collapsed:
        return ""

    if strip_prefix:
        for prefix in COMMENT_PREFIXES:
            if collapsed.startswith(prefix):
                collapsed = collapsed[len(prefix):].lstrip()
                break

    return WHITESPACE_RE.sub(" ", collapsed).strip()


def normalize_block(text: str, strip_prefix: bool) -> list[str]:
    normalized = []
    for line in text.splitlines():
        cleaned = normalize_line(line, strip_prefix)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def restore_flattened_comment_lines(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped or "\n" in stripped:
        return [stripped] if stripped else []

    restored = [part.strip() for part in FLATTENED_SPLIT_RE.split(stripped) if part.strip()]
    if len(restored) <= 1:
        return [stripped]
    return restored


def normalized_comment_variants(text: str, strip_prefix: bool) -> list[list[str]]:
    variants: list[list[str]] = []
    seen = set()

    candidates = [text]
    restored = restore_flattened_comment_lines(text)
    if restored:
        candidates.append("\n".join(restored))

    for candidate in candidates:
        normalized = normalize_block(candidate, strip_prefix)
        key = tuple(normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        variants.append(normalized)

    return variants


def clip_block_comment(line: str, start: int, marker: str) -> str:
    end_marker = "*/" if marker == "/*" else "-->"
    end = line.find(end_marker, start + len(marker))
    if end < 0:
        return line[start:]
    return line[start:end + len(end_marker)]


def find_unquoted_marker(line: str, markers: tuple[str, ...]) -> tuple[int, str] | None:
    quote = ""
    escaped = False

    for index, char in enumerate(line):
        if quote:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = ""
            continue

        if char in {'"', "'"}:
            quote = char
            continue

        for marker in markers:
            if line.startswith(marker, index):
                return index, marker

    return None


def detect_single_line_comment(line: str) -> tuple[str, str] | None:
    found = find_unquoted_marker(line, ("//", "/*", "<!--"))
    if found is not None:
        position, marker = found
        if marker in {"/*", "<!--"}:
            return clip_block_comment(line, position, marker), marker
        return line[position:], marker

    stripped = line.lstrip()
    for marker in ("--", "#", ";"):
        if stripped.startswith(marker):
            return stripped, marker

    return None


def extract_comment_blocks(path: Path) -> list[CommentBlock]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    blocks: list[CommentBlock] = []
    lines = content.splitlines()
    in_block = False
    end_marker = ""
    current_lines: list[str] = []
    current_start = 0
    single_comment_lines: list[str] = []
    single_comment_start = 0
    single_comment_marker = ""

    def flush_single_comment_block(end_line: int) -> None:
        nonlocal single_comment_lines, single_comment_start, single_comment_marker
        if not single_comment_lines:
            return
        blocks.append(
            CommentBlock(
                text="\n".join(single_comment_lines),
                start_line=single_comment_start,
                end_line=end_line,
            )
        )
        single_comment_lines = []
        single_comment_start = 0
        single_comment_marker = ""

    for line_number, line in enumerate(lines, start=1):
        if in_block:
            flush_single_comment_block(line_number - 1)
            current_lines.append(line)
            if end_marker and end_marker in line:
                blocks.append(
                    CommentBlock(
                        text="\n".join(current_lines),
                        start_line=current_start,
                        end_line=line_number,
                    )
                )
                current_lines = []
                current_start = 0
                in_block = False
                end_marker = ""
            continue

        block_marker = None
        block_position = -1
        first_marker = find_unquoted_marker(line, ("//", "/*", "<!--"))
        if first_marker is not None:
            block_position, block_marker = first_marker

        if block_marker in {"/*", "<!--"}:
            flush_single_comment_block(line_number - 1)
            current_start = line_number
            current_lines = [clip_block_comment(line, block_position, block_marker)]
            end_marker = "*/" if block_marker == "/*" else "-->"
            if end_marker in current_lines[0] and current_lines[0].find(end_marker) > 0:
                blocks.append(
                    CommentBlock(
                        text=current_lines[0],
                        start_line=current_start,
                        end_line=line_number,
                    )
                )
                current_lines = []
                current_start = 0
                end_marker = ""
            else:
                in_block = True
            continue

        single_line = detect_single_line_comment(line)
        if single_line:
            comment_text, marker = single_line
            if not single_comment_lines:
                single_comment_lines = [comment_text]
                single_comment_start = line_number
                single_comment_marker = marker
            elif marker == single_comment_marker:
                single_comment_lines.append(comment_text)
            else:
                flush_single_comment_block(line_number - 1)
                single_comment_lines = [comment_text]
                single_comment_start = line_number
                single_comment_marker = marker
            continue

        flush_single_comment_block(line_number - 1)

    flush_single_comment_block(len(lines))

    return blocks


def build_repo_index(repo_path: Path) -> dict[tuple[bool, str], list[MatchLocation]]:
    index: dict[tuple[bool, str], list[MatchLocation]] = defaultdict(list)

    for source_file in iter_source_files(repo_path):
        relative_path = str(source_file.relative_to(repo_path))
        for block in extract_comment_blocks(source_file):
            for strip_prefix in (False, True):
                normalized_lines = normalize_block(block.text, strip_prefix)
                if not normalized_lines:
                    continue

                joined = "\n".join(normalized_lines)
                index[(strip_prefix, joined)].append(
                    MatchLocation(
                        file_path=relative_path,
                        start_line=block.start_line,
                        end_line=block.end_line,
                        match_type="block_stripped" if strip_prefix else "block",
                    )
                )
                if len(normalized_lines) > 1:
                    index[(strip_prefix, flat_key(normalized_lines))].append(
                        MatchLocation(
                            file_path=relative_path,
                            start_line=block.start_line,
                            end_line=block.end_line,
                            match_type="block_flat_stripped" if strip_prefix else "block_flat",
                        )
                    )

                for offset, line in enumerate(normalized_lines):
                    index[(strip_prefix, line)].append(
                        MatchLocation(
                            file_path=relative_path,
                            start_line=block.start_line + offset,
                            end_line=block.start_line + offset,
                            match_type="line_stripped" if strip_prefix else "line",
                        )
                    )

    return index


def dedupe_locations(locations: list[MatchLocation]) -> list[MatchLocation]:
    unique = []
    seen = set()
    for location in locations:
        key = (
            location.file_path,
            location.start_line,
            location.end_line,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(location)
    return unique


def find_locations(
    comment_text: str,
    repo_index: dict[tuple[bool, str], list[MatchLocation]],
    max_matches: int,
) -> list[MatchLocation]:
    collected: list[MatchLocation] = []
    for strip_prefix in (False, True):
        for normalized_lines in normalized_comment_variants(comment_text, strip_prefix):
            collected.extend(repo_index.get((strip_prefix, "\n".join(normalized_lines)), []))
            if len(normalized_lines) > 1:
                collected.extend(repo_index.get((strip_prefix, flat_key(normalized_lines)), []))

            if len(normalized_lines) == 1:
                collected.extend(repo_index.get((strip_prefix, normalized_lines[0]), []))

    return dedupe_locations(collected)[:max_matches]


def build_unique_entries(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["project_name"], row["comment_text"])
        entry = grouped.get(key)
        if entry is None:
            grouped[key] = {
                "project_name": row["project_name"],
                "comment_text": row["comment_text"],
                "input_count": "1",
            }
        else:
            entry["input_count"] = str(int(entry["input_count"]) + 1)
    return list(grouped.values())


def output_fieldnames(mode: str, input_fieldnames: list[str]) -> list[str]:
    location_fields = [
        "repo_path",
        "match_status",
        "match_type",
        "file_path",
        "start_line",
        "end_line",
    ]
    if mode == "rows":
        return ["input_row"] + input_fieldnames + location_fields
    return ["project_name", "comment_text", "input_count"] + location_fields


def write_result_rows(
    writer: csv.DictWriter,
    base_row: dict[str, str],
    locations: list[MatchLocation],
    repo_path: Path | None,
    mode: str,
    input_fieldnames: list[str],
) -> None:
    repo_value = str(repo_path) if repo_path is not None else ""

    if mode == "rows":
        row_prefix = {"input_row": base_row["_row_number"]}
        for field in input_fieldnames:
            row_prefix[field] = base_row.get(field, "")
    else:
        row_prefix = {
            "project_name": base_row["project_name"],
            "comment_text": base_row["comment_text"],
            "input_count": base_row["input_count"],
        }

    if not repo_path:
        writer.writerow(
            row_prefix
            | {
                "repo_path": "",
                "match_status": "repo_not_found",
                "match_type": "",
                "file_path": "",
                "start_line": "",
                "end_line": "",
            }
        )
        return

    if not locations:
        writer.writerow(
            row_prefix
            | {
                "repo_path": repo_value,
                "match_status": "not_found",
                "match_type": "",
                "file_path": "",
                "start_line": "",
                "end_line": "",
            }
        )
        return

    for location in locations:
        writer.writerow(
            row_prefix
            | {
                "repo_path": repo_value,
                "match_status": "matched",
                "match_type": location.match_type,
                "file_path": location.file_path,
                "start_line": str(location.start_line),
                "end_line": str(location.end_line),
            }
        )


def main() -> int:
    args = parse_args()
    input_fieldnames, rows = load_input_rows(Path(args.csv_path), set(args.project))
    entries = build_unique_entries(rows) if args.mode == "unique" else rows
    mapping = load_mapping(args.mapping)

    output_handle = (
        sys.stdout
        if args.output == "-"
        else Path(args.output).open("w", encoding="utf-8", newline="")
    )

    try:
        writer = csv.DictWriter(
            output_handle,
            fieldnames=output_fieldnames(args.mode, input_fieldnames),
        )
        writer.writeheader()

        projects = sorted({entry["project_name"] for entry in entries})
        repo_indexes: dict[str, dict[tuple[bool, str], list[MatchLocation]]] = {}
        repo_paths: dict[str, Path | None] = {}

        for project_name in projects:
            repo_path = resolve_repo_path(project_name, args.repos_root, mapping)
            repo_paths[project_name] = repo_path
            if repo_path is None:
                print(
                    f"[warn] repository not found for {project_name}",
                    file=sys.stderr,
                )
                continue

            print(f"[info] indexing {project_name}: {repo_path}", file=sys.stderr)
            repo_indexes[project_name] = build_repo_index(repo_path)

        for entry in entries:
            project_name = entry["project_name"]
            repo_path = repo_paths.get(project_name)
            repo_index = repo_indexes.get(project_name, {})
            locations = find_locations(
                entry["comment_text"],
                repo_index,
                args.max_matches,
            ) if repo_path else []
            write_result_rows(
                writer,
                entry,
                locations,
                repo_path,
                args.mode,
                input_fieldnames,
            )
    finally:
        if output_handle is not sys.stdout:
            output_handle.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
