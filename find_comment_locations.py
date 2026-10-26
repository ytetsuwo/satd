#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess


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

LOCATION_FIELDS = (
    "repo_path",
    "match_status",
    "match_type",
    "file_path",
    "start_line",
    "end_line",
)
CONTEXT_FIELDS = ("code_before", "code_after")
BLAME_FIELDS = (
    "blame_status",
    "blame_commit_ids",
    "blame_line_commits",
    "blame_report_path",
    "blame_error",
)


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


@dataclass(frozen=True)
class BlameLine:
    line_number: int
    commit_id: str
    author: str
    author_mail: str
    author_time: str
    summary: str
    text: str


@dataclass(frozen=True)
class CommitArtifact:
    commit_id: str
    commit_text_path: str
    diff_patch_path: str
    error: str


@dataclass(frozen=True)
class BlameResult:
    status: str
    commit_ids: tuple[str, ...]
    line_commits: str
    report_path: str
    error: str


RepoIndex = dict[tuple[bool, str], list[MatchLocation]]


def flat_key(lines: list[str]) -> str:
    return " ".join(lines)


def match_type_priority(match_type: str) -> int:
    priorities = {
        "block": 0,
        "block_flat": 1,
        "block_stripped": 2,
        "block_flat_stripped": 3,
        "line": 4,
        "line_stripped": 5,
    }
    return priorities.get(match_type, 99)


def sanitize_path_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return sanitized or "unknown"


def normalize_commit_id(value: str) -> str:
    normalized = value.lstrip("^")
    if re.fullmatch(r"0{40}", normalized):
        return "UNCOMMITTED"
    return normalized


def format_git_timestamp(value: str) -> str:
    if not value.isdigit():
        return ""
    return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()


def empty_blame_fields() -> dict[str, str]:
    return {field: "" for field in BLAME_FIELDS}


def non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer value: {value!r}") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("value must be 0 or greater")
    return number


def empty_context_fields() -> dict[str, str]:
    return {field: "" for field in CONTEXT_FIELDS}


def run_git(repo_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def git_error(completed: subprocess.CompletedProcess[str], fallback: str) -> str:
    return completed.stderr.strip() or completed.stdout.strip() or fallback


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
        default="rows",
        help="Output one row per input CSV row or per unique comment.",
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
    parser.add_argument(
        "--blame",
        action="store_true",
        help="Run git blame for matched comment lines and append commit metadata.",
    )
    parser.add_argument(
        "--context-lines",
        type=non_negative_int,
        default=0,
        help=(
            "Number of source lines to include before and after each matched "
            "comment in code_before / code_after. Default is 0 (disabled)."
        ),
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("comment_git_artifacts"),
        help=(
            "Directory used with --blame to save commit metadata, patches, "
            "and per-match blame reports."
        ),
    )
    parser.add_argument(
        "--no-artifacts",
        action="store_true",
        help=(
            "With --blame, skip saving commit metadata, patches, and blame "
            "reports. The blame columns are still written to the output CSV."
        ),
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


def has_substantive_comment_text(text: str) -> bool:
    return bool(normalize_block(text, True))


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
        if not has_substantive_comment_text(candidate):
            continue
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

    def add_block(text: str, start_line: int, end_line: int) -> None:
        blocks.append(
            CommentBlock(
                text=text,
                start_line=start_line,
                end_line=end_line,
            )
        )

    def flush_single_comment_block(end_line: int) -> None:
        nonlocal single_comment_lines, single_comment_start, single_comment_marker
        if not single_comment_lines:
            return
        add_block(
            "\n".join(single_comment_lines),
            single_comment_start,
            end_line,
        )
        single_comment_lines = []
        single_comment_start = 0
        single_comment_marker = ""

    for line_number, line in enumerate(lines, start=1):
        if in_block:
            flush_single_comment_block(line_number - 1)
            current_lines.append(line)
            if end_marker and end_marker in line:
                add_block(
                    "\n".join(current_lines),
                    current_start,
                    line_number,
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
                add_block(current_lines[0], current_start, line_number)
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


def add_index_match(
    index: RepoIndex,
    key: tuple[bool, str],
    file_path: str,
    start_line: int,
    end_line: int,
    match_type: str,
) -> None:
    index[key].append(
        MatchLocation(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            match_type=match_type,
        )
    )


def build_repo_index(repo_path: Path) -> RepoIndex:
    index: RepoIndex = defaultdict(list)

    for source_file in iter_source_files(repo_path):
        relative_path = str(source_file.relative_to(repo_path))
        for block in extract_comment_blocks(source_file):
            if not has_substantive_comment_text(block.text):
                continue
            for strip_prefix in (False, True):
                normalized_lines = normalize_block(block.text, strip_prefix)
                if not normalized_lines:
                    continue

                joined = "\n".join(normalized_lines)
                suffix = "_stripped" if strip_prefix else ""
                add_index_match(
                    index,
                    (strip_prefix, joined),
                    relative_path,
                    block.start_line,
                    block.end_line,
                    f"block{suffix}",
                )
                if len(normalized_lines) > 1:
                    add_index_match(
                        index,
                        (strip_prefix, flat_key(normalized_lines)),
                        relative_path,
                        block.start_line,
                        block.end_line,
                        f"block_flat{suffix}",
                    )

                for offset, line in enumerate(normalized_lines):
                    add_index_match(
                        index,
                        (strip_prefix, line),
                        relative_path,
                        block.start_line + offset,
                        block.start_line + offset,
                        f"line{suffix}",
                    )

    return index


def contains_location(outer: MatchLocation, inner: MatchLocation) -> bool:
    return outer.start_line <= inner.start_line and outer.end_line >= inner.end_line


def dedupe_locations(locations: list[MatchLocation]) -> list[MatchLocation]:
    grouped: dict[str, dict[tuple[int, int], MatchLocation]] = defaultdict(dict)
    for location in locations:
        key = (location.start_line, location.end_line)
        existing = grouped[location.file_path].get(key)
        if existing is None or (
            match_type_priority(location.match_type)
            < match_type_priority(existing.match_type)
        ):
            grouped[location.file_path][key] = location

    unique = []
    for file_path in sorted(grouped):
        file_locations = sorted(
            grouped[file_path].values(),
            key=lambda loc: (
                loc.start_line,
                -loc.end_line,
                match_type_priority(loc.match_type),
            ),
        )
        kept: list[MatchLocation] = []
        for location in file_locations:
            skip = False
            for index, existing in enumerate(kept):
                if contains_location(existing, location) and (
                    match_type_priority(existing.match_type)
                    <= match_type_priority(location.match_type)
                ):
                    skip = True
                    break

                if contains_location(location, existing) and (
                    match_type_priority(location.match_type)
                    < match_type_priority(existing.match_type)
                ):
                    kept[index] = location
                    skip = True
                    break

            if not skip:
                kept.append(location)

        unique.extend(kept)

    return unique


def prefer_strongest_match_type(locations: list[MatchLocation]) -> list[MatchLocation]:
    if not locations:
        return []

    best_priority = min(match_type_priority(location.match_type) for location in locations)
    return [
        location
        for location in locations
        if match_type_priority(location.match_type) == best_priority
    ]


def is_git_repo(
    repo_path: Path,
    cache: dict[str, tuple[bool, str]],
) -> tuple[bool, str]:
    cache_key = str(repo_path.resolve())
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        completed = run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    except FileNotFoundError:
        result = (False, "git command not found")
        cache[cache_key] = result
        return result

    if completed.returncode == 0 and completed.stdout.strip() == "true":
        result = (True, "")
    else:
        result = (False, git_error(completed, "not a git repository"))
    cache[cache_key] = result
    return result


def parse_blame_porcelain(output: str) -> list[BlameLine]:
    lines: list[BlameLine] = []
    current_commit_id = ""
    current_line_number = 0
    metadata: dict[str, str] = {}

    for raw_line in output.splitlines():
        if raw_line.startswith("\t"):
            if not current_commit_id:
                continue
            lines.append(
                BlameLine(
                    line_number=current_line_number,
                    commit_id=normalize_commit_id(current_commit_id),
                    author=metadata.get("author", ""),
                    author_mail=metadata.get("author-mail", ""),
                    author_time=metadata.get("author-time", ""),
                    summary=metadata.get("summary", ""),
                    text=raw_line[1:],
                )
            )
            current_commit_id = ""
            current_line_number = 0
            metadata = {}
            continue

        if not current_commit_id:
            parts = raw_line.split()
            if len(parts) >= 3 and re.fullmatch(r"\^?[0-9a-f]{40}", parts[0]):
                current_commit_id = parts[0]
                current_line_number = int(parts[2])
            continue

        if raw_line == "boundary":
            metadata["boundary"] = "true"
            continue

        if " " in raw_line:
            key, value = raw_line.split(" ", 1)
            metadata[key] = value

    return lines


def summarize_line_commits(lines: list[BlameLine]) -> str:
    if not lines:
        return ""

    summarized: list[str] = []
    start = lines[0].line_number
    end = lines[0].line_number
    commit_id = lines[0].commit_id

    for line in lines[1:]:
        if line.commit_id == commit_id and line.line_number == end + 1:
            end = line.line_number
            continue

        if start == end:
            summarized.append(f"{start}={commit_id}")
        else:
            summarized.append(f"{start}-{end}={commit_id}")
        start = line.line_number
        end = line.line_number
        commit_id = line.commit_id

    if start == end:
        summarized.append(f"{start}={commit_id}")
    else:
        summarized.append(f"{start}-{end}={commit_id}")
    return ";".join(summarized)


def unique_commit_ids(lines: list[BlameLine]) -> list[str]:
    commit_ids: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if line.commit_id in seen:
            continue
        seen.add(line.commit_id)
        commit_ids.append(line.commit_id)
    return commit_ids


def save_commit_artifacts(
    repo_path: Path,
    project_name: str,
    commit_id: str,
    artifacts_dir: Path,
    cache: dict[tuple[str, str], CommitArtifact],
) -> CommitArtifact:
    cache_key = (str(repo_path.resolve()), commit_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if commit_id == "UNCOMMITTED":
        artifact = CommitArtifact(
            commit_id=commit_id,
            commit_text_path="",
            diff_patch_path="",
            error="line is not committed yet",
        )
        cache[cache_key] = artifact
        return artifact

    project_dir = artifacts_dir / "commits" / sanitize_path_component(project_name) / commit_id
    project_dir.mkdir(parents=True, exist_ok=True)
    commit_text_path = project_dir / "commit.txt"
    diff_patch_path = project_dir / "diff.patch"

    error = ""
    try:
        commit_text = run_git(
            repo_path,
            ["show", "--stat", "--summary", "--format=fuller", "--no-patch", commit_id],
        )
        diff_text = run_git(repo_path, ["show", "--format=", "--patch", commit_id])
    except FileNotFoundError:
        error = "git command not found"
    else:
        if commit_text.returncode != 0:
            error = git_error(commit_text, "git show failed")
        elif diff_text.returncode != 0:
            error = git_error(diff_text, "git show failed")
        else:
            commit_text_path.write_text(commit_text.stdout, encoding="utf-8")
            diff_patch_path.write_text(diff_text.stdout, encoding="utf-8")

    artifact = CommitArtifact(
        commit_id=commit_id,
        commit_text_path=str(commit_text_path) if commit_text_path.exists() else "",
        diff_patch_path=str(diff_patch_path) if diff_patch_path.exists() else "",
        error=error,
    )
    cache[cache_key] = artifact
    return artifact


def blame_line_payload(line: BlameLine) -> dict[str, object]:
    return {
        "line_number": line.line_number,
        "commit_id": line.commit_id,
        "author": line.author,
        "author_mail": line.author_mail,
        "author_time": line.author_time,
        "author_time_iso": format_git_timestamp(line.author_time),
        "summary": line.summary,
        "text": line.text,
    }


def commit_artifact_payload(artifact: CommitArtifact) -> dict[str, str]:
    return {
        "commit_id": artifact.commit_id,
        "commit_text_path": artifact.commit_text_path,
        "diff_patch_path": artifact.diff_patch_path,
        "error": artifact.error,
    }


def save_blame_report(
    repo_path: Path,
    project_name: str,
    location: MatchLocation,
    blame_lines: list[BlameLine],
    commit_artifacts: list[CommitArtifact],
    artifacts_dir: Path,
) -> Path:
    report_dir = artifacts_dir / "matches" / sanitize_path_component(project_name)
    report_dir.mkdir(parents=True, exist_ok=True)

    digest_source = (
        f"{project_name}\n{location.file_path}\n{location.start_line}\n{location.end_line}"
    )
    digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:12]
    report_path = report_dir / (
        f"{sanitize_path_component(Path(location.file_path).name)}_"
        f"L{location.start_line}-L{location.end_line}_{digest}.json"
    )

    payload = {
        "project_name": project_name,
        "repo_path": str(repo_path),
        "file_path": location.file_path,
        "start_line": location.start_line,
        "end_line": location.end_line,
        "commit_ids": unique_commit_ids(blame_lines),
        "line_blame": [blame_line_payload(line) for line in blame_lines],
        "commit_artifacts": [
            commit_artifact_payload(artifact) for artifact in commit_artifacts
        ],
    }
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def failed_blame_result(status: str, error: str) -> BlameResult:
    return BlameResult(
        status=status,
        commit_ids=(),
        line_commits="",
        report_path="",
        error=error,
    )


def blame_location(
    repo_path: Path,
    project_name: str,
    location: MatchLocation,
    artifacts_dir: Path | None,
    repo_status_cache: dict[str, tuple[bool, str]],
    commit_artifact_cache: dict[tuple[str, str], CommitArtifact],
) -> BlameResult:
    is_repo, repo_error = is_git_repo(repo_path, repo_status_cache)
    if not is_repo:
        return failed_blame_result("not_git_repo", repo_error)

    try:
        completed = run_git(
            repo_path,
            [
                "blame",
                "--line-porcelain",
                "-L",
                f"{location.start_line},{location.end_line}",
                "--",
                location.file_path,
            ],
        )
    except FileNotFoundError:
        return failed_blame_result("git_not_found", "git command not found")

    if completed.returncode != 0:
        return failed_blame_result(
            "blame_failed",
            git_error(completed, "git blame failed"),
        )

    blame_lines = parse_blame_porcelain(completed.stdout)
    if not blame_lines:
        return failed_blame_result("blame_failed", "git blame returned no line data")

    commit_ids = unique_commit_ids(blame_lines)
    report_path = ""
    artifact_errors: list[str] = []
    if artifacts_dir is not None:
        commit_artifacts = [
            save_commit_artifacts(
                repo_path,
                project_name,
                commit_id,
                artifacts_dir,
                commit_artifact_cache,
            )
            for commit_id in commit_ids
        ]
        artifact_errors = [
            f"{artifact.commit_id}: {artifact.error}"
            for artifact in commit_artifacts
            if artifact.error
        ]
        report_path = str(
            save_blame_report(
                repo_path,
                project_name,
                location,
                blame_lines,
                commit_artifacts,
                artifacts_dir,
            )
        )

    return BlameResult(
        status="blamed",
        commit_ids=tuple(commit_ids),
        line_commits=summarize_line_commits(blame_lines),
        report_path=report_path,
        error=" | ".join(artifact_errors),
    )


def load_repo_file_lines(
    repo_path: Path,
    file_path: str,
    cache: dict[tuple[str, str], list[str] | None],
) -> list[str] | None:
    cache_key = (str(repo_path.resolve()), file_path)
    if cache_key in cache:
        return cache[cache_key]

    try:
        content = (repo_path / file_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        cache[cache_key] = None
        return None

    lines = content.splitlines()
    cache[cache_key] = lines
    return lines


def extract_code_context(
    repo_path: Path,
    location: MatchLocation,
    context_lines: int,
    cache: dict[tuple[str, str], list[str] | None],
) -> tuple[str, str]:
    if context_lines <= 0:
        return "", ""

    lines = load_repo_file_lines(repo_path, location.file_path, cache)
    if not lines:
        return "", ""

    before_end = max(0, min(location.start_line - 1, len(lines)))
    before_start = max(0, before_end - context_lines)
    after_start = max(0, min(location.end_line, len(lines)))
    after_end = min(len(lines), after_start + context_lines)

    code_before = "\n".join(lines[before_start:before_end]).strip()
    code_after = "\n".join(lines[after_start:after_end]).strip()
    return code_before, code_after


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

    return prefer_strongest_match_type(dedupe_locations(collected))[:max_matches]


def count_comment_occurrences(rows: list[dict[str, str]]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        counts[(row["project_name"], row["comment_text"])] += 1
    return dict(counts)


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


def output_fieldnames(
    mode: str,
    input_fieldnames: list[str],
    include_blame: bool,
    include_context: bool,
) -> list[str]:
    fields = list(LOCATION_FIELDS)
    if include_context:
        fields.extend(CONTEXT_FIELDS)
    if include_blame:
        fields.extend(BLAME_FIELDS)
    if mode == "rows":
        return ["input_row"] + input_fieldnames + fields
    return ["project_name", "comment_text", "input_count"] + fields


def build_row_prefix(
    base_row: dict[str, str],
    mode: str,
    input_fieldnames: list[str],
) -> dict[str, str]:
    if mode == "rows":
        prefix = {"input_row": base_row["_row_number"]}
        for field in input_fieldnames:
            prefix[field] = base_row.get(field, "")
        return prefix

    return {
        "project_name": base_row["project_name"],
        "comment_text": base_row["comment_text"],
        "input_count": base_row["input_count"],
    }


def match_fields(
    repo_path: str,
    status: str,
    location: MatchLocation | None = None,
) -> dict[str, str]:
    fields = {"repo_path": repo_path, "match_status": status}
    if location is None:
        fields.update(
            match_type="",
            file_path="",
            start_line="",
            end_line="",
        )
    else:
        fields.update(
            match_type=location.match_type,
            file_path=location.file_path,
            start_line=str(location.start_line),
            end_line=str(location.end_line),
        )
    return fields


def blame_fields(result: BlameResult | None) -> dict[str, str]:
    if result is None:
        return empty_blame_fields()
    return {
        "blame_status": result.status,
        "blame_commit_ids": ";".join(result.commit_ids),
        "blame_line_commits": result.line_commits,
        "blame_report_path": result.report_path,
        "blame_error": result.error,
    }


def code_context_fields(result: tuple[str, str] | None) -> dict[str, str]:
    if result is None:
        return empty_context_fields()
    code_before, code_after = result
    return {"code_before": code_before, "code_after": code_after}


def write_status_row(
    writer: csv.DictWriter,
    row_prefix: dict[str, str],
    repo_path: str,
    status: str,
    include_blame: bool,
    include_context: bool,
) -> None:
    row = row_prefix | match_fields(repo_path, status)
    if include_blame:
        row |= empty_blame_fields()
    if include_context:
        row |= empty_context_fields()
    writer.writerow(row)


def write_result_rows(
    writer: csv.DictWriter,
    base_row: dict[str, str],
    locations: list[MatchLocation],
    blame_results: list[BlameResult] | None,
    include_blame: bool,
    context_results: list[tuple[str, str]] | None,
    include_context: bool,
    repo_path: Path | None,
    mode: str,
    input_fieldnames: list[str],
) -> None:
    row_prefix = build_row_prefix(base_row, mode, input_fieldnames)

    if repo_path is None:
        write_status_row(
            writer, row_prefix, "", "repo_not_found", include_blame, include_context
        )
        return

    repo_value = str(repo_path)
    if not locations:
        write_status_row(
            writer, row_prefix, repo_value, "not_found", include_blame, include_context
        )
        return

    for index, location in enumerate(locations):
        blame_result = None
        if include_blame and blame_results is not None and index < len(blame_results):
            blame_result = blame_results[index]

        context_result = None
        if include_context and context_results is not None and index < len(context_results):
            context_result = context_results[index]

        row = row_prefix | match_fields(repo_value, "matched", location)
        if include_context:
            row |= code_context_fields(context_result)
        if include_blame:
            row |= blame_fields(blame_result)
        writer.writerow(row)


def build_repo_indexes(
    projects: list[str],
    repos_root: Path | None,
    mapping: dict[str, Path],
) -> tuple[dict[str, RepoIndex], dict[str, Path | None]]:
    repo_indexes: dict[str, RepoIndex] = {}
    repo_paths: dict[str, Path | None] = {}

    for project_name in projects:
        repo_path = resolve_repo_path(project_name, repos_root, mapping)
        repo_paths[project_name] = repo_path
        if repo_path is None:
            print(
                f"[warn] repository not found for {project_name}",
                file=sys.stderr,
            )
            continue

        print(f"[info] indexing {project_name}: {repo_path}", file=sys.stderr)
        repo_indexes[project_name] = build_repo_index(repo_path)

    return repo_indexes, repo_paths


def location_key(repo_path: Path, location: MatchLocation) -> tuple[str, str, int, int]:
    return (
        str(repo_path.resolve()),
        location.file_path,
        location.start_line,
        location.end_line,
    )


def select_locations(
    entry: dict[str, str],
    repo_path: Path,
    repo_index: RepoIndex,
    max_matches: int,
    row_comment_counts: dict[tuple[str, str], int],
    assigned_counts: dict[tuple[str, str], int],
    location_cache: dict[tuple[str, str], list[MatchLocation]],
    mode: str,
) -> list[MatchLocation]:
    key = (entry["project_name"], entry["comment_text"])
    if key not in location_cache:
        limit = max_matches
        if mode == "rows":
            limit = max(limit, row_comment_counts.get(key, 0))
        location_cache[key] = find_locations(entry["comment_text"], repo_index, limit)

    locations = location_cache[key]
    if mode != "rows":
        return locations

    if row_comment_counts.get(key, 0) > 1:
        used_count = assigned_counts[key]
        selected = locations[used_count:used_count + 1]
        if selected:
            assigned_counts[key] += 1
        return selected

    return locations[:1]


def collect_blame_results(
    locations: list[MatchLocation],
    repo_path: Path,
    project_name: str,
    artifacts_dir: Path | None,
    repo_status_cache: dict[str, tuple[bool, str]],
    commit_artifact_cache: dict[tuple[str, str], CommitArtifact],
    blame_cache: dict[tuple[str, str, int, int], BlameResult],
) -> list[BlameResult]:
    results: list[BlameResult] = []
    for location in locations:
        key = location_key(repo_path, location)
        result = blame_cache.get(key)
        if result is None:
            result = blame_location(
                repo_path,
                project_name,
                location,
                artifacts_dir,
                repo_status_cache,
                commit_artifact_cache,
            )
            blame_cache[key] = result
        results.append(result)
    return results


def collect_context_results(
    locations: list[MatchLocation],
    repo_path: Path,
    context_lines: int,
    file_lines_cache: dict[tuple[str, str], list[str] | None],
    code_context_cache: dict[tuple[str, str, int, int], tuple[str, str]],
) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for location in locations:
        key = location_key(repo_path, location)
        context = code_context_cache.get(key)
        if context is None:
            context = extract_code_context(
                repo_path,
                location,
                context_lines,
                file_lines_cache,
            )
            code_context_cache[key] = context
        results.append(context)
    return results


def write_entries(
    writer: csv.DictWriter,
    entries: list[dict[str, str]],
    args: argparse.Namespace,
    input_fieldnames: list[str],
    row_comment_counts: dict[tuple[str, str], int],
    repo_paths: dict[str, Path | None],
    repo_indexes: dict[str, RepoIndex],
    artifacts_dir: Path | None,
    include_context: bool,
) -> None:
    assigned_location_counts: dict[tuple[str, str], int] = defaultdict(int)
    location_cache: dict[tuple[str, str], list[MatchLocation]] = {}
    repo_status_cache: dict[str, tuple[bool, str]] = {}
    commit_artifact_cache: dict[tuple[str, str], CommitArtifact] = {}
    blame_cache: dict[tuple[str, str, int, int], BlameResult] = {}
    code_context_cache: dict[tuple[str, str, int, int], tuple[str, str]] = {}
    file_lines_cache: dict[tuple[str, str], list[str] | None] = {}

    for entry in entries:
        project_name = entry["project_name"]
        repo_path = repo_paths.get(project_name)
        locations: list[MatchLocation] = []
        blame_results: list[BlameResult] | None = [] if args.blame else None
        context_results: list[tuple[str, str]] | None = [] if include_context else None

        if repo_path is not None:
            locations = select_locations(
                entry,
                repo_path,
                repo_indexes.get(project_name, {}),
                args.max_matches,
                row_comment_counts,
                assigned_location_counts,
                location_cache,
                args.mode,
            )
            if args.blame:
                blame_results = collect_blame_results(
                    locations,
                    repo_path,
                    project_name,
                    artifacts_dir,
                    repo_status_cache,
                    commit_artifact_cache,
                    blame_cache,
                )
            if include_context:
                context_results = collect_context_results(
                    locations,
                    repo_path,
                    args.context_lines,
                    file_lines_cache,
                    code_context_cache,
                )

        write_result_rows(
            writer,
            entry,
            locations,
            blame_results,
            args.blame,
            context_results,
            include_context,
            repo_path,
            args.mode,
            input_fieldnames,
        )


def main() -> int:
    args = parse_args()
    input_fieldnames, rows = load_input_rows(Path(args.csv_path), set(args.project))
    entries = build_unique_entries(rows) if args.mode == "unique" else rows
    row_comment_counts = count_comment_occurrences(rows) if args.mode == "rows" else {}
    mapping = load_mapping(args.mapping)
    artifacts_dir = (
        args.artifacts_dir.resolve() if args.blame and not args.no_artifacts else None
    )
    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
    include_context = args.context_lines > 0

    output_handle = (
        sys.stdout
        if args.output == "-"
        else Path(args.output).open("w", encoding="utf-8", newline="")
    )

    try:
        writer = csv.DictWriter(
            output_handle,
            fieldnames=output_fieldnames(
                args.mode,
                input_fieldnames,
                args.blame,
                include_context,
            ),
        )
        writer.writeheader()

        projects = sorted({entry["project_name"] for entry in entries})
        repo_indexes, repo_paths = build_repo_indexes(
            projects,
            args.repos_root,
            mapping,
        )
        write_entries(
            writer,
            entries,
            args,
            input_fieldnames,
            row_comment_counts,
            repo_paths,
            repo_indexes,
            artifacts_dir,
            include_context,
        )
    finally:
        if output_handle is not sys.stdout:
            output_handle.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
