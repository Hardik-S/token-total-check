from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from token_total_check.cli import InvalidInput, evaluate


def row(identifier="r", input_tokens=0, output_tokens=0, total_tokens=0, **extra):
    value = {"id": identifier, "input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens}
    value.update(extra)
    return json.dumps(value, ensure_ascii=True)


class EvaluationTests(unittest.TestCase):
    def evaluate_text(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "fixture.jsonl"
            path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
            return evaluate(path)

    def test_empty_and_inclusive_bounds(self):
        self.assertEqual(self.evaluate_text(""), ({"status": "valid", "record_count": 0, "mismatch_lines": []}, 0))
        line = row("edge", 1_000_000_000_000, 1_000_000_000_000, 2_000_000_000_000)
        self.assertEqual(self.evaluate_text(line), ({"status": "valid", "record_count": 1, "mismatch_lines": []}, 0))

    def test_exact_large_integer_math_and_sorted_physical_line_numbers(self):
        exact = row("exact", 10**12, 10**12, 2 * 10**12)
        text = "\r\n".join([row("first", 1, 2, 8), exact, row("third", 9, 0, 7)]) + "\r\n"
        self.assertEqual(self.evaluate_text(text), ({"status": "total_mismatch", "record_count": 3, "mismatch_lines": [1, 3]}, 1))

    def test_cr_lf_crlf_delimiters_and_final_terminator(self):
        for delimiter in ("\r", "\n", "\r\n"):
            with self.subTest(delimiter=repr(delimiter)):
                self.assertEqual(self.evaluate_text(row("a") + delimiter + row("b") + delimiter)[0]["record_count"], 2)

    def test_unicode_exact_ids_without_normalization(self):
        composed = "é"
        decomposed = "e\u0301"
        self.assertEqual(self.evaluate_text(row(composed) + "\n" + row(decomposed))[0]["record_count"], 2)
        self.assert_invalid(row(composed) + "\n" + row(composed))

    def assert_invalid(self, text):
        with self.assertRaises(InvalidInput):
            self.evaluate_text(text)

    def test_bool_and_float_are_rejected(self):
        for field, value in (("input_tokens", True), ("output_tokens", 1.0), ("total_tokens", 0.0)):
            with self.subTest(field=field, value=value):
                self.assert_invalid(row(**{field: value}))

    def test_bounds_and_wrong_schema(self):
        for field, value in (("input_tokens", -1), ("input_tokens", 10**12 + 1), ("output_tokens", 10**12 + 1), ("total_tokens", -1), ("total_tokens", 2 * 10**12 + 1)):
            self.assert_invalid(row(**{field: value}))
        self.assert_invalid(row(extra="x"))
        self.assert_invalid(json.dumps({"id": "r", "input_tokens": 0, "output_tokens": 0}))
        self.assert_invalid("[]")
        self.assert_invalid('{"id":"","input_tokens":0,"output_tokens":0,"total_tokens":0}')

    def test_strict_json_and_jsonl(self):
        malformed = [
            "\n", "  \r\n", "not json", '{"id":"a","id":"b","input_tokens":0,"output_tokens":0,"total_tokens":0}',
            '{"id":"a","input_tokens":NaN,"output_tokens":0,"total_tokens":0}',
            '{"id":"\\ud800","input_tokens":0,"output_tokens":0,"total_tokens":0}',
            '{"id":"a","input_tokens":0,"output_tokens":0,"total_tokens":0}\u2028{"id":"b","input_tokens":0,"output_tokens":0,"total_tokens":0}',
        ]
        for text in malformed:
            with self.subTest(text=text[:24]):
                self.assert_invalid(text)
        self.assert_invalid(b'{"id":"\xff","input_tokens":0,"output_tokens":0,"total_tokens":0}')

    def test_decoder_and_walker_depth_are_rejected(self):
        deep = "{" * 1500 + "}" * 1500
        self.assert_invalid(deep)
        # Deeply nested data in a row fails the exact schema; neither decoder nor
        # recursive Unicode validation is allowed to escape as a traceback.
        self.assert_invalid('{"id":"a","input_tokens":0,"output_tokens":0,"total_tokens":0,"extra":' + "[" * 1100 + "0" + "]" * 1100 + "}")

    def test_late_invalid_row_prevents_partial_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "input.jsonl"
            path.write_text(row("ok") + "\n" + "{}", encoding="utf-8")
            with self.assertRaises(InvalidInput):
                evaluate(path)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(pathlib.Path(__file__).resolve().parents[1] / "src")
        return subprocess.run([sys.executable, "-m", "token_total_check.cli", *args], capture_output=True, text=True, env=env, check=False)

    def test_exit_codes_and_exact_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "input.jsonl"
            path.write_text(row("a", 2, 3, 5), encoding="utf-8")
            valid = self.run_cli(str(path))
            self.assertEqual((valid.returncode, valid.stdout, valid.stderr), (0, '{"status":"valid","record_count":1,"mismatch_lines":[]}\n', ""))
            path.write_text(row("a", 2, 3, 6), encoding="utf-8")
            mismatch = self.run_cli(str(path))
            self.assertEqual((mismatch.returncode, mismatch.stdout, mismatch.stderr), (1, '{"status":"total_mismatch","record_count":1,"mismatch_lines":[1]}\n', ""))
            path.write_text('{"id":"private-id","input_tokens":true,"output_tokens":3,"total_tokens":4}', encoding="utf-8")
            invalid = self.run_cli(str(path))
            self.assertEqual((invalid.returncode, invalid.stdout, invalid.stderr), (2, '{"status":"invalid_input"}\n', ""))
            self.assertNotIn("private-id", invalid.stdout + invalid.stderr)
            missing = self.run_cli(str(path) + ".missing")
            self.assertEqual((missing.returncode, missing.stdout, missing.stderr), (2, '{"status":"invalid_input"}\n', ""))

    def test_help_and_bad_argv(self):
        for args in (("-h",), ("--help",)):
            result = self.run_cli(*args)
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            self.assertIn("usage:", result.stdout)
        for args in ((), ("one", "two"), ("--unknown",)):
            result = self.run_cli(*args)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (2, '{"status":"invalid_input"}\n', ""))


if __name__ == "__main__":
    unittest.main()
