#!/usr/bin/env python3
"""Tests for commit-size-checker-cli. Standard library only.

Run: python3 tests/test_commit_size_checker.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "commit_size_checker.py"
sys.path.insert(0, str(ROOT / "src"))

import commit_size_checker as csc  # noqa: E402


SMALL_DIFF = """\
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,5 @@
 import sys
+import os
+
 
 def main():
-    print("old")
+    print("new")
"""

BIG_DIFF = """\
diff --git a/big.py b/big.py
index 1111111..2222222 100644
--- a/big.py
+++ b/big.py
@@ -1,1 +1,60 @@
""" + "".join("+line %d\n" % i for i in range(60))

NEW_FILE_DIFF = """\
diff --git a/new.py b/new.py
new file mode 100644
index 0000000..2222222
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+def hello():
+    return "hi"
+
"""

DELETED_FILE_DIFF = """\
diff --git a/old.py b/old.py
deleted file mode 100644
index 2222222..0000000
--- a/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def gone():
-    pass
-
"""

BINARY_DIFF = """\
diff --git a/logo.png b/logo.png
index 1111111..2222222 100644
Binary files a/logo.png and b/logo.png differ
"""

PLAIN_DIFF = """\
--- a/notes.txt
+++ b/notes.txt
@@ -1,2 +1,2 @@
 hello
-world
+there
"""


class TestParseDiff(unittest.TestCase):
    def test_small_diff_counts(self):
        files = csc.parse_diff(SMALL_DIFF)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["path"], "app.py")
        self.assertEqual(files[0]["added"], 3)
        self.assertEqual(files[0]["removed"], 1)
        self.assertFalse(files[0]["binary"])

    def test_big_diff_counts(self):
        files = csc.parse_diff(BIG_DIFF)
        self.assertEqual(files[0]["added"], 60)
        self.assertEqual(files[0]["removed"], 0)

    def test_new_file(self):
        files = csc.parse_diff(NEW_FILE_DIFF)
        self.assertEqual(files[0]["path"], "new.py")
        self.assertEqual(files[0]["added"], 3)
        self.assertEqual(files[0]["removed"], 0)

    def test_deleted_file(self):
        files = csc.parse_diff(DELETED_FILE_DIFF)
        self.assertEqual(files[0]["path"], "old.py")
        self.assertEqual(files[0]["added"], 0)
        self.assertEqual(files[0]["removed"], 3)

    def test_binary_file_not_counted(self):
        files = csc.parse_diff(BINARY_DIFF)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0]["binary"])
        self.assertEqual(files[0]["added"], 0)
        self.assertEqual(files[0]["removed"], 0)

    def test_plain_diff_without_git_header(self):
        files = csc.parse_diff(PLAIN_DIFF)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["path"], "notes.txt")
        self.assertEqual(files[0]["added"], 1)
        self.assertEqual(files[0]["removed"], 1)

    def test_empty_diff(self):
        self.assertEqual(csc.parse_diff(""), [])

    def test_headers_not_counted(self):
        # "+++" and "---" lines are headers, not added/removed lines.
        files = csc.parse_diff(SMALL_DIFF)
        self.assertEqual(files[0]["added"], 3)

    def test_no_newline_marker_not_counted(self):
        diff = SMALL_DIFF + "\\ No newline at end of file\n"
        files = csc.parse_diff(diff)
        self.assertEqual(files[0]["added"], 3)
        self.assertEqual(files[0]["removed"], 1)

    def test_context_lines_not_counted(self):
        diff = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,4 +1,4 @@
 context one
 context two
-old
+new
 context three
"""
        files = csc.parse_diff(diff)
        self.assertEqual(files[0]["added"], 1)
        self.assertEqual(files[0]["removed"], 1)

    def test_multiple_files_in_order(self):
        files = csc.parse_diff(SMALL_DIFF + BIG_DIFF)
        self.assertEqual([f["path"] for f in files], ["app.py", "big.py"])

    def test_lines_that_look_like_additions_inside_content(self):
        # A "+" inside a context line or a hunk header is not a change.
        diff = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,3 @@
 x = "a+b"
++y = 1
"""
        files = csc.parse_diff(diff)
        self.assertEqual(files[0]["added"], 1)

    def test_rename_uses_new_path(self):
        diff = """\
diff --git a/oldname.py b/newname.py
similarity index 90%
rename from oldname.py
rename to newname.py
--- a/oldname.py
+++ b/newname.py
@@ -1,2 +1,2 @@
-old line
+new line
"""
        files = csc.parse_diff(diff)
        self.assertEqual(files[0]["path"], "newname.py")
        self.assertEqual(files[0]["added"], 1)
        self.assertEqual(files[0]["removed"], 1)


class TestCheck(unittest.TestCase):
    def test_under_limit(self):
        files = csc.parse_diff(SMALL_DIFF)
        total, over_total, over_files = csc.check(files, 500, None)
        self.assertEqual(total, 4)
        self.assertFalse(over_total)
        self.assertEqual(over_files, [])

    def test_over_limit(self):
        files = csc.parse_diff(BIG_DIFF)
        total, over_total, over_files = csc.check(files, 50, None)
        self.assertEqual(total, 60)
        self.assertTrue(over_total)

    def test_exactly_at_limit_passes(self):
        files = csc.parse_diff(BIG_DIFF)
        total, over_total, _ = csc.check(files, 60, None)
        self.assertFalse(over_total)

    def test_one_over_limit_fails(self):
        files = csc.parse_diff(BIG_DIFF)
        _, over_total, _ = csc.check(files, 59, None)
        self.assertTrue(over_total)

    def test_per_file_limit(self):
        files = csc.parse_diff(SMALL_DIFF + BIG_DIFF)
        _, _, over_files = csc.check(files, 500, 10)
        self.assertEqual([f["path"] for f in over_files], ["big.py"])

    def test_per_file_exactly_at_limit_passes(self):
        files = csc.parse_diff(SMALL_DIFF)
        _, _, over_files = csc.check(files, 500, 4)
        self.assertEqual(over_files, [])

    def test_empty_diff_total_zero(self):
        total, over_total, over_files = csc.check([], 500, None)
        self.assertEqual(total, 0)
        self.assertFalse(over_total)
        self.assertEqual(over_files, [])

    def test_binary_files_do_not_add_to_total(self):
        files = csc.parse_diff(BINARY_DIFF)
        total, over_total, _ = csc.check(files, 0, None)
        self.assertEqual(total, 0)
        self.assertFalse(over_total)


class TestRun(unittest.TestCase):
    def test_small_diff_passes(self):
        self.assertEqual(csc.run(["--limit", "500"], stdin=SMALL_DIFF), 0)

    def test_big_diff_fails(self):
        self.assertEqual(csc.run(["--limit", "50"], stdin=BIG_DIFF), 1)

    def test_default_limit_is_500(self):
        # 60 lines: passes at the default 500, fails at 50.
        self.assertEqual(csc.run([], stdin=BIG_DIFF), 0)

    def test_per_file_flag(self):
        self.assertEqual(
            csc.run(["--per-file", "10"], stdin=SMALL_DIFF + BIG_DIFF), 1
        )
        self.assertEqual(
            csc.run(["--per-file", "100"], stdin=SMALL_DIFF + BIG_DIFF), 0
        )

    def test_negative_limit_is_usage_error(self):
        self.assertEqual(csc.run(["--limit", "-1"], stdin=SMALL_DIFF), 2)

    def test_negative_per_file_is_usage_error(self):
        self.assertEqual(
            csc.run(["--per-file", "-1"], stdin=SMALL_DIFF), 2
        )

    def test_missing_file_is_usage_error(self):
        self.assertEqual(csc.run(["no-such.diff"]), 2)

    def test_two_git_modes_is_usage_error(self):
        self.assertEqual(
            csc.run(["--staged", "--commit", "HEAD"], stdin=""), 2
        )

    def test_git_mode_with_file_is_usage_error(self):
        self.assertEqual(
            csc.run(["--staged", "changes.diff"], stdin=""), 2
        )

    def test_empty_diff_passes(self):
        self.assertEqual(csc.run([], stdin=""), 0)

    def test_json_output_parses(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = csc.run(["--json", "--limit", "50"], stdin=BIG_DIFF)
        self.assertEqual(code, 1)
        result = json.loads(buffer.getvalue())
        self.assertEqual(result["total"], 60)
        self.assertEqual(result["limit"], 50)
        self.assertFalse(result["pass"])
        self.assertEqual(result["files"][0]["path"], "big.py")
        self.assertEqual(result["files"][0]["added"], 60)

    def test_diff_file_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changes.diff"
            path.write_text(SMALL_DIFF)
            self.assertEqual(csc.run([str(path)]), 0)
            self.assertEqual(csc.run(["--limit", "2", str(path)]), 1)


class TestGitModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.email", "t@t.t"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.name", "Test"],
            check=True,
        )
        (self.repo / "a.py").write_text("one\ntwo\n")
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "first"],
            check=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _run_in_repo(self, argv):
        old = os.getcwd()
        os.chdir(self.repo)
        try:
            return csc.run(argv)
        finally:
            os.chdir(old)

    def test_staged_diff(self):
        (self.repo / "a.py").write_text("one\ntwo\nthree\n")
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "."], check=True
        )
        # 1 added line: passes at limit 500, fails at limit 0.
        self.assertEqual(self._run_in_repo(["--staged"]), 0)
        self.assertEqual(self._run_in_repo(["--staged", "--limit", "0"]), 1)

    def test_range_diff(self):
        (self.repo / "a.py").write_text("one\ntwo\nthree\nfour\n")
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "second"],
            check=True,
        )
        self.assertEqual(
            self._run_in_repo(["--range", "HEAD~1..HEAD"]), 0
        )
        self.assertEqual(
            self._run_in_repo(["--range", "HEAD~1..HEAD", "--limit", "1"]), 1
        )

    def test_commit_diff(self):
        (self.repo / "a.py").write_text("one\ntwo\nthree\n")
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "second"],
            check=True,
        )
        self.assertEqual(self._run_in_repo(["--commit", "HEAD"]), 0)
        self.assertEqual(
            self._run_in_repo(["--commit", "HEAD", "--limit", "0"]), 1
        )

    def test_git_mode_outside_repo_is_usage_error(self):
        with tempfile.TemporaryDirectory() as other:
            old = os.getcwd()
            os.chdir(other)
            try:
                self.assertEqual(csc.run(["--staged"]), 2)
            finally:
                os.chdir(old)


class TestExamples(unittest.TestCase):
    def test_example_files_match_fresh_run(self):
        examples = ROOT / "examples"
        saved = (examples / "sample-output.txt").read_text()
        result = subprocess.run(
            [sys.executable, str(SRC), "--limit", "50",
             str(examples / "small.diff")],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(result.stdout.strip(), saved)
        result = subprocess.run(
            [sys.executable, str(SRC), "--limit", "50",
             str(examples / "big.diff")],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(result.stdout.strip(), saved)

    def test_run_example_script(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_readme_quoted_outputs_are_real(self):
        readme = (ROOT / "README.md").read_text()
        saved = (ROOT / "examples" / "sample-output.txt").read_text()
        for line in saved.strip().splitlines():
            if line.startswith("Total:") or line.startswith("PASS") \
                    or line.startswith("FAIL"):
                self.assertIn(line, readme, line)


class TestRepoHygiene(unittest.TestCase):
    def test_stdlib_only_imports(self):
        allowed = {
            "argparse", "contextlib", "json", "re", "subprocess",
            "sys", "pathlib", "io", "os", "tempfile", "unittest",
        }
        for path in list((ROOT / "src").rglob("*.py")) + list(
            (ROOT / "tests").rglob("*.py")
        ):
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("import "):
                    for name in line[7:].split(","):
                        top = name.strip().split(".")[0].split(" ")[0]
                        self.assertIn(
                            top,
                            allowed | {"commit_size_checker"},
                            "%s in %s" % (top, path),
                        )
                elif line.startswith("from "):
                    top = line.split()[1].split(".")[0]
                    self.assertIn(
                        top,
                        allowed | {"commit_size_checker"},
                        "%s in %s" % (top, path),
                    )

    def test_no_placeholders_or_secrets(self):
        banned = (
            "TODO",
            "FIXME",
            "lorem",
            "coming soon",
            "API_KEY",
            "api_key",
            "password =",
        )
        # The tests directory is excluded from this scan: the test file
        # itself names the banned words in its own check list, and it
        # uses temp paths. The shipped content is what must be clean.
        # .git is excluded too: GitHub's checkout ships sample hooks
        # under .git/hooks/ that contain "TODO" (Day 21 CI failure).
        shipped = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in str(path)
            and ".git" not in path.parts
            and "tests" not in path.parts
        ]
        for path in shipped:
            text = path.read_text(errors="ignore")
            for word in banned:
                self.assertNotIn(word, text, "%s in %s" % (word, path))

    def test_no_absolute_paths(self):
        # Same exclusion as the placeholder scan: the test file itself
        # names temp paths in its own check list.
        shipped = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in str(path)
            and ".git" not in path.parts
            and "tests" not in path.parts
        ]
        for path in shipped:
            text = path.read_text(errors="ignore")
            self.assertNotIn(
                "/home/hatch", text, "absolute path in %s" % path
            )
            self.assertNotIn("/tmp/", text, "absolute path in %s" % path)

    def test_gitignore_lists_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")


if __name__ == "__main__":
    unittest.main()
