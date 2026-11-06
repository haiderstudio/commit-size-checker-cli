#!/usr/bin/env python3
"""Check a diff stays under your line limit, fail CI when it is too big.

Run: python3 src/commit_size_checker.py --staged
     python3 src/commit_size_checker.py --range main..HEAD
     python3 src/commit_size_checker.py --commit HEAD
     python3 src/commit_size_checker.py changes.diff
     git diff | python3 src/commit_size_checker.py

The tool reads a unified diff, counts added and removed lines per file,
and reports the total. The default limit is 500 lines (added + removed).
It exits 1 when the total is over the limit, or when any single file is
over the per-file limit you set with --per-file, so it can fail a CI run.

It is report-only: it never changes a file, never stages anything, and
never makes a commit. It only reads the diff you give it (or asks git
for one) and prints a report.

Exit codes: 0 when the diff is under every limit, 1 when it is over a
limit, 2 for a usage or input problem (missing file, bad limit, git not
available, not inside a git repo for --staged / --range / --commit).

Python standard library only.
"""

import argparse
import subprocess
import sys
from pathlib import Path

VERSION = "1.0.0"
DEFAULT_LIMIT = 500


class DiffError(Exception):
    """A problem reading the diff or running git."""


def parse_diff(text):
    """Parse a unified diff into per-file counts.

    Returns a list of dicts, one per file, in the order they appear:
    {"path": str, "added": int, "removed": int, "binary": bool}.
    Lines starting with "+" count as added and "-" as removed, except
    the "+++" and "---" header lines. A file with no header lines at
    all is reported under the path "(unknown file)".
    """
    files = []
    current = None

    def new_file(path):
        entry = {"path": path, "added": 0, "removed": 0, "binary": False}
        files.append(entry)
        return entry

    for line in text.splitlines():
        if line.startswith("diff --git "):
            # "diff --git a/old b/new" — the new path is the last word,
            # minus its leading "b/".
            parts = line.split(" ")
            new_path = parts[-1]
            if new_path.startswith("b/"):
                new_path = new_path[2:]
            current = new_file(new_path)
        elif line.startswith("+++ "):
            path = line[4:].strip()
            if path == "/dev/null":
                # Deleted file: keep the old path from the "---" line.
                continue
            if path.startswith("b/"):
                path = path[2:]
            if current is None:
                current = new_file(path)
            elif current["path"] == "(unknown file)":
                current["path"] = path
            else:
                current["path"] = path
        elif line.startswith("--- "):
            path = line[4:].strip()
            if path == "/dev/null":
                continue
            if path.startswith("a/"):
                path = path[2:]
            if current is None:
                current = new_file(path)
        elif line.startswith("Binary files "):
            if current is None:
                current = new_file("(unknown file)")
            current["binary"] = True
        elif line.startswith("+") and not line.startswith("+++"):
            if current is None:
                current = new_file("(unknown file)")
            current["added"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            if current is None:
                current = new_file("(unknown file)")
            current["removed"] += 1
        # Hunk headers ("@@ ... @@"), context lines, and "\ No newline
        # at end of file" are not counted.

    return files


def check(files, limit, per_file):
    """Check the counts against the limits.

    Returns (total, over_total, over_files) where over_total is True
    when the total is over the limit, and over_files is the list of
    files over the per-file limit (empty when no per-file limit set).
    """
    total = sum(entry["added"] + entry["removed"] for entry in files)
    over_total = total > limit
    over_files = []
    if per_file is not None:
        over_files = [
            entry
            for entry in files
            if entry["added"] + entry["removed"] > per_file
        ]
    return total, over_total, over_files


def run_git_diff(args):
    """Ask git for a diff. Returns the diff text."""
    if args.staged:
        command = ["git", "diff", "--cached"]
    elif args.range:
        command = ["git", "diff", args.range]
    else:  # args.commit
        command = ["git", "show", "--format=", args.commit]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        raise DiffError("git is not installed or not on PATH")
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        message = detail[0] if detail else "git failed"
        raise DiffError("git failed: %s" % message)
    return result.stdout


def validate_source_args(args):
    """Check the diff-source flags make sense together."""
    git_modes = [args.staged, args.range is not None, args.commit is not None]
    if sum(1 for mode in git_modes if mode) > 1:
        raise DiffError("use only one of --staged, --range, --commit")
    if any(git_modes) and args.diff_file is not None:
        raise DiffError("do not name a diff file with a git mode")


def read_diff_input(args):
    """Read the diff text from git, a file, or standard input."""
    validate_source_args(args)
    git_modes = [args.staged, args.range is not None, args.commit is not None]
    if any(git_modes):
        return run_git_diff(args)
    if args.diff_file is not None:
        path = Path(args.diff_file)
        if not path.is_file():
            raise DiffError("no such file: %s" % args.diff_file)
        return path.read_text(errors="replace")
    if sys.stdin.isatty():
        raise DiffError(
            "no diff given: name a diff file, use a git mode, "
            "or pipe a diff to standard input"
        )
    return sys.stdin.read()


def format_report(files, total, limit, per_file, over_total, over_files):
    """Build the plain-text report lines."""
    lines = []
    for entry in files:
        size = entry["added"] + entry["removed"]
        if entry["binary"]:
            lines.append("%s: binary file, not counted" % entry["path"])
        else:
            lines.append(
                "%s: +%d -%d = %d"
                % (entry["path"], entry["added"], entry["removed"], size)
            )
    if not files:
        lines.append("No changes found.")
    added = sum(entry["added"] for entry in files)
    removed = sum(entry["removed"] for entry in files)
    lines.append(
        "Total: +%d -%d = %d lines (limit %d)" % (added, removed, total, limit)
    )
    if over_total:
        lines.append(
            "FAIL — %d lines is over the limit of %d."
            % (total, limit)
        )
    if over_files:
        lines.append(
            "FAIL — %d file(s) over the per-file limit of %d:"
            % (len(over_files), per_file)
        )
        for entry in over_files:
            lines.append(
                "  %s: %d lines"
                % (entry["path"], entry["added"] + entry["removed"])
            )
    if not over_total and not over_files:
        lines.append("PASS — under the limit.")
    return "\n".join(lines) + "\n"


def build_parser():
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="commit_size_checker",
        description=(
            "Check a diff stays under your line limit. Reads a unified "
            "diff from a file, from git, or from standard input, counts "
            "added and removed lines per file, and exits 1 when the "
            "diff is over the limit."
        ),
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + VERSION
    )
    parser.add_argument(
        "diff_file",
        nargs="?",
        help="unified diff file to check (omit to read standard input)",
    )
    source = parser.add_argument_group("diff source (pick at most one)")
    source.add_argument(
        "--staged",
        action="store_true",
        help="check the staged changes (git diff --cached)",
    )
    source.add_argument(
        "--range",
        metavar="A..B",
        help="check the diff between two revisions (git diff A..B)",
    )
    source.add_argument(
        "--commit",
        metavar="REV",
        help="check one commit's diff (git show REV)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        metavar="N",
        help="total line limit (added + removed), default %(default)s",
    )
    parser.add_argument(
        "--per-file",
        type=int,
        default=None,
        metavar="N",
        help="also fail when any single file is over N lines",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON instead of plain text",
    )
    return parser


def run(argv=None, stdin=None):
    """Run the checker. Returns the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.limit < 0:
        print("error: --limit must be 0 or more", file=sys.stderr)
        return 2
    if args.per_file is not None and args.per_file < 0:
        print("error: --per-file must be 0 or more", file=sys.stderr)
        return 2
    try:
        validate_source_args(args)
    except DiffError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if stdin is not None:
        text = stdin
    else:
        try:
            text = read_diff_input(args)
        except DiffError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
    files = parse_diff(text)
    total, over_total, over_files = check(files, args.limit, args.per_file)
    failed = over_total or bool(over_files)
    if args.json:
        import json

        result = {
            "total": total,
            "limit": args.limit,
            "per_file_limit": args.per_file,
            "pass": not failed,
            "files": [
                {
                    "path": entry["path"],
                    "added": entry["added"],
                    "removed": entry["removed"],
                    "binary": entry["binary"],
                }
                for entry in files
            ],
        }
        print(json.dumps(result, indent=2))
    else:
        print(
            format_report(
                files, total, args.limit, args.per_file, over_total, over_files
            ),
            end="",
        )
    return 1 if failed else 0


def main():
    sys.exit(run())


if __name__ == "__main__":
    main()
