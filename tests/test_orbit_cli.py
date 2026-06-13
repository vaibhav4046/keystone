"""Tests for core/orbit_cli.py, the runtime Orbit Local CLI driver.

Pure stdlib (unittest plus mock) so it runs with no glab binary, no DuckDB, and
no third-party packages present, which is exactly the state of a fresh checkout.
The real glab process is mocked; these tests assert the contract Keystone
depends on: the canonical command form, graceful degradation when glab is
absent, defensive parsing, and the transcript capture the status panel reads.

Run:  python -m unittest tests.test_orbit_cli   (from D:\\project\\keystone)
"""

import subprocess
import unittest
from unittest import mock

from core import orbit_cli

_SAVED_ORBIT_BINARY = None


def setUpModule():
    # These tests assert the documented `glab orbit local ...` driver form; pin it
    # so they pass regardless of a KEYSTONE_ORBIT_BINARY set in the environment.
    global _SAVED_ORBIT_BINARY
    _SAVED_ORBIT_BINARY = orbit_cli.ORBIT_BINARY
    orbit_cli.ORBIT_BINARY = None


def tearDownModule():
    orbit_cli.ORBIT_BINARY = _SAVED_ORBIT_BINARY


def _completed(argv, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


class CommandFormTests(unittest.TestCase):
    def setUp(self):
        orbit_cli.clear_transcript()

    def test_missing_binary_degrades_gracefully(self):
        with mock.patch.object(orbit_cli, "glab_available", return_value=False):
            res = orbit_cli.sql("SELECT name FROM gl_definition LIMIT 3")
        self.assertFalse(res.ok)
        self.assertIsNone(res.returncode)
        self.assertIn("not found", res.error)
        self.assertEqual(res.source, "glab orbit local")
        # The attempt is still recorded so the status panel can show it.
        self.assertEqual(len(orbit_cli.get_transcript()), 1)

    def test_canonical_command_form_for_sql(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["shell"] = kwargs.get("shell")
            return _completed(argv, 0, stdout="[]")

        with mock.patch.object(orbit_cli, "glab_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run", side_effect=fake_run):
            orbit_cli.sql("SELECT name FROM gl_definition LIMIT 3")

        self.assertEqual(
            captured["argv"],
            [orbit_cli.GLAB_BINARY, "orbit", "local", "sql",
             "SELECT name FROM gl_definition LIMIT 3"],
        )
        # Never invoke a shell; the query is one argv element.
        self.assertFalse(captured["shell"])

    def test_canonical_command_form_for_schema_table(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return _completed(argv, 0, stdout="")

        with mock.patch.object(orbit_cli, "glab_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run", side_effect=fake_run):
            orbit_cli.schema("gl_definition")

        self.assertEqual(
            captured["argv"],
            [orbit_cli.GLAB_BINARY, "orbit", "local", "schema", "gl_definition"],
        )

    def test_direct_orbit_binary_driver(self):
        """With KEYSTONE_ORBIT_BINARY set, drive the orbit binary directly as
        `orbit <sub>` (fast, offline), not via glab."""
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return _completed(argv, 0, stdout="[]")

        with mock.patch.object(orbit_cli, "ORBIT_BINARY", "/opt/orbit"), \
                mock.patch.object(orbit_cli, "cli_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run", side_effect=fake_run):
            res = orbit_cli.sql("SELECT 1")
        self.assertEqual(captured["argv"], ["/opt/orbit", "sql", "SELECT 1"])
        self.assertEqual(res.source, "orbit local")
        self.assertTrue(res.ok)


class ExecutionResultTests(unittest.TestCase):
    def setUp(self):
        orbit_cli.clear_transcript()

    def test_sql_success_parses_json_array(self):
        rows = '[{"name": "parse"}, {"name": "build"}]'
        with mock.patch.object(orbit_cli, "glab_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run",
                                  return_value=_completed([], 0, stdout=rows)):
            res = orbit_cli.sql("SELECT name FROM gl_definition")
        self.assertTrue(res.ok)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.parsed, [{"name": "parse"}, {"name": "build"}])
        self.assertGreaterEqual(res.duration_ms, 0.0)
        self.assertEqual(len(orbit_cli.get_transcript()), 1)

    def test_sql_nonzero_exit_is_not_ok(self):
        with mock.patch.object(orbit_cli, "glab_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run",
                                  return_value=_completed([], 2, stderr="boom")):
            res = orbit_cli.sql("SELECT 1")
        self.assertFalse(res.ok)
        self.assertEqual(res.returncode, 2)
        self.assertIn("exited 2", res.error)
        self.assertIsNone(res.parsed)

    def test_timeout_is_caught(self):
        def boom(*a, **k):
            raise subprocess.TimeoutExpired(cmd="glab", timeout=6.0)

        with mock.patch.object(orbit_cli, "glab_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run", side_effect=boom):
            res = orbit_cli.schema()
        self.assertFalse(res.ok)
        self.assertIn("timed out", res.error)

    def test_oserror_is_caught(self):
        with mock.patch.object(orbit_cli, "glab_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run",
                                  side_effect=OSError("permission denied")):
            res = orbit_cli.sql("SELECT 1")
        self.assertFalse(res.ok)
        self.assertIn("failed to run glab", res.error)


class ParseRowsTests(unittest.TestCase):
    def test_json_array(self):
        self.assertEqual(
            orbit_cli._parse_rows('[{"a": 1}]'), [{"a": 1}]
        )

    def test_ndjson(self):
        out = orbit_cli._parse_rows('{"a": 1}\n{"a": 2}')
        self.assertEqual(out, [{"a": 1}, {"a": 2}])

    def test_pipe_table(self):
        text = "name | kind\nparse | function\nbuild | function"
        self.assertEqual(
            orbit_cli._parse_rows(text),
            [{"name": "parse", "kind": "function"},
             {"name": "build", "kind": "function"}],
        )

    def test_whitespace_table_skips_rule_lines(self):
        text = "name kind\n+----+----+\nparse function"
        self.assertEqual(
            orbit_cli._parse_rows(text), [{"name": "parse", "kind": "function"}]
        )

    def test_empty_returns_none(self):
        self.assertIsNone(orbit_cli._parse_rows(""))
        self.assertIsNone(orbit_cli._parse_rows("   \n  "))

    def test_unparseable_returns_none(self):
        self.assertIsNone(orbit_cli._parse_rows("totally not a table"))


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        orbit_cli.clear_transcript()

    def test_transcript_is_bounded(self):
        with mock.patch.object(orbit_cli, "glab_available", return_value=False):
            for _ in range(orbit_cli._TRANSCRIPT_MAX_ENTRIES + 10):
                orbit_cli.sql("SELECT 1")
        self.assertEqual(
            len(orbit_cli.get_transcript()), orbit_cli._TRANSCRIPT_MAX_ENTRIES
        )

    def test_transcript_lines_render(self):
        with mock.patch.object(orbit_cli, "glab_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run",
                                  return_value=_completed([], 0, stdout="[]")):
            orbit_cli.sql("SELECT name FROM gl_definition LIMIT 3")
        lines = orbit_cli.transcript_lines()
        self.assertEqual(len(lines), 1)
        self.assertIn("glab orbit local sql", lines[0])
        self.assertIn("OK", lines[0])

    def test_status_entry_is_serialisable_and_secret_free(self):
        with mock.patch.object(orbit_cli, "glab_available", return_value=True), \
                mock.patch.object(orbit_cli.subprocess, "run",
                                  return_value=_completed([], 0, stdout="[]")):
            orbit_cli.sql("SELECT 1")
        entry = orbit_cli.get_transcript()[-1]
        self.assertEqual(
            set(entry),
            {"subcommand", "command", "returncode", "ok", "duration_ms",
             "source", "stdout", "stderr", "error", "ts"},
        )


if __name__ == "__main__":
    unittest.main()
