# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the diff file, standard input, or git output you name, and it never changes a file, never stages anything, and never makes a commit. It writes nothing except the report on standard output (and usage errors on standard error).

If you find a case where the tool changes a file, or reports a count that does not match the real diff, please open an issue describing the exact commands and input. Do not include any real secret in the report.
