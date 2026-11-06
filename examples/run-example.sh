#!/bin/sh
# Run the checker on the bundled examples.
# Run from the repo root: sh examples/run-example.sh
# The big-diff run exits 1 because the diff is over the limit on purpose —
# that is the expected result here.
set -e
cd "$(dirname "$0")/.."
echo "--- small diff, limit 50 ---"
python3 src/commit_size_checker.py --limit 50 examples/small.diff
echo "--- big diff, limit 50 ---"
python3 src/commit_size_checker.py --limit 50 examples/big.diff || true
echo "--- big diff as JSON ---"
python3 src/commit_size_checker.py --limit 50 --json examples/big.diff || true
