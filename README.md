# commit-size-checker-cli

Check a diff stays under your line limit, fail CI when it is too big.

[![CI](https://github.com/haiderstudio/commit-size-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/commit-size-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`commit_size_checker` reads a unified diff, counts added and removed
lines per file, and reports the total against a limit you set. The
default limit is 500 lines (added + removed). It exits 1 when the diff
is over the limit, so it can fail a CI run before a huge change lands.

- It reads a diff from a file, from standard input, or straight from
  git: `--staged` checks staged changes, `--range A..B` checks the diff
  between two revisions, `--commit REV` checks one commit's diff.
- `--limit N` sets the total line limit. `--per-file N` also fails when
  any single file is over N lines.
- `--json` prints the result as JSON instead of plain text, for scripts.
- Binary files are reported but not counted — a changed image adds
  zero lines to the total.
- It is report-only and runs fully offline: it never changes a file,
  never stages anything, never makes a commit, sends nothing anywhere,
  and needs no API key.

## What it does NOT do

- It does not block a commit by itself. It only reports and exits 1;
  your CI or hook decides what to do with that.
- It does not count lines of code, only diff lines. A moved block
  counts as removed plus added, because that is what the diff shows.
- It does not check commit messages, branch names, or file sizes.
  Commit message length is a different job, and branch names are
  covered by branch-name-checker-cli.
- It does not rewrite, split, or squash anything. If a diff is too
  big, splitting it is your job.

## Who it is for

Anyone who wants small, reviewable changes: a team that agreed on a
500-line limit and wants CI to enforce it, a developer checking their
own work before pushing, or anyone adding a one-line guard to a
pre-commit hook. If the diff is under the limit, you get a short
PASS; if it is over, the report names the files that pushed it over.

## How this differs from similar tools

Size limits today live inside review bots and big CI setups, not as a
small local check. The nearest GitHub results for this job are tiny:
medeirosinacio/git-commit-size-checker-extension (2 stars) is a
JavaScript browser extension that checks commit *message* length, a
different job; A2-ai/staged-size-checker (0 stars) is a Rust tool that
checks staged files as a pre-commit hook; and the "large commit
checker" results are a 2015 Gradle plugin (1 star). None of them is a
Python standard-library CLI that reads any unified diff, counts lines
per file, and fails CI on a limit you set.

This tool does that one narrow job: a Python standard-library-only
CLI, no install beyond Python, no browser, no hook framework, no
review bot — one number, one check.

## Install

Python standard library only — no packages to download. Clone the
repo and run it in place:

```sh
git clone https://github.com/haiderstudio/commit-size-checker-cli.git
cd commit-size-checker-cli
```

Python 3.10 or newer.

## Usage

Check a diff file, limit 50:

```sh
python3 src/commit_size_checker.py --limit 50 examples/small.diff
```

Real output:

```text
app.py: +3 -1 = 4
Total: +3 -1 = 4 lines (limit 50)
PASS — under the limit.
```

The command exits 0. The same output is saved in
`examples/sample-output.txt`.

Check a diff that is over the limit:

```sh
python3 src/commit_size_checker.py --limit 50 examples/big.diff
```

Real output:

```text
big.py: +60 -0 = 60
Total: +60 -0 = 60 lines (limit 50)
FAIL — 60 lines is over the limit of 50.
```

The command exits 1.

Check staged changes, with a per-file limit:

```sh
python3 src/commit_size_checker.py --staged --per-file 100
```

Check one commit, as JSON:

```sh
python3 src/commit_size_checker.py --commit HEAD --json
```

Real output (on a small commit):

```text
{
  "total": 1,
  "limit": 500,
  "per_file_limit": null,
  "pass": true,
  "files": [
    {
      "path": "a.py",
      "added": 1,
      "removed": 0,
      "binary": false
    }
  ]
}
```

Check a diff from a pipe:

```sh
git diff | python3 src/commit_size_checker.py --limit 300
```

## Examples

### 1. Fail CI on a diff that is too big

```sh
python3 src/commit_size_checker.py --limit 50 examples/big.diff
echo $?
```

```text
1
```

The exit code is 1 when the diff is over the limit. Put the same
command in CI (reading the diff from a pipe or a file) and the build
fails until the change is split into smaller pieces. Under the limit
the same command prints `PASS — under the limit.` and exits 0:

### 2. One file over the per-file limit

`examples/big.diff` is a single file with 60 added lines:

```sh
python3 src/commit_size_checker.py --limit 500 --per-file 50 examples/big.diff
```

```text
big.py: +60 -0 = 60
Total: +60 -0 = 60 lines (limit 500)
FAIL — 1 file(s) over the per-file limit of 50:
  big.py: 60 lines
```

The total is under 500, but the one file is over 50, so the command
exits 1. Use `--per-file` when one huge file is the problem, not the
whole change.

## How it is tested

Run the tests from the repo root:

```sh
python3 tests/test_commit_size_checker.py
```

44 tests, standard library `unittest` only. They cover diff parsing
(new, deleted, renamed, and binary files, plain `diff -u` output,
headers and context lines never counted), the limit checks (exactly
at the limit passes, one over fails, per-file limits, binary files
add zero), the CLI (exit codes 0/1/2, JSON output, usage errors),
the git modes against a real temporary git repo (`--staged`,
`--range`, `--commit`, and outside a repo), and the bundled examples
(the committed `sample-output.txt` is compared against a fresh run).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea — keep
commits small by checking diff size — is a common team rule; the
code, tests, and examples here are original.
