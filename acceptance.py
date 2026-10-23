"""Installed-package acceptance check, independent of the source checkout."""

from __future__ import annotations

import importlib.metadata
import json
import os
import pathlib
import subprocess
import sys
import sysconfig
import tempfile


def main() -> int:
    dist = importlib.metadata.distribution("token-total-check")
    assert dist.version == "0.1.0", dist.version
    console = pathlib.Path(sysconfig.get_path("scripts")) / ("token-total-check.exe" if os.name == "nt" else "token-total-check")
    assert console.is_file(), str(console)
    root = pathlib.Path(__file__).resolve().parent
    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    outside = tempfile.gettempdir()
    probe = subprocess.run(
        [sys.executable, "-c", "import token_total_check; print(token_total_check.__file__); print(token_total_check.__version__)"],
        capture_output=True,
        text=True,
        env=env,
        cwd=outside,
        check=False,
    )
    assert probe.returncode == 0 and probe.stderr == "", probe.stderr
    module_path, installed_version = probe.stdout.splitlines()
    assert installed_version == "0.1.0", installed_version
    assert not pathlib.Path(module_path).resolve().is_relative_to(root.resolve()), module_path
    cases = [
        ("valid", '{"id":"a","input_tokens":0,"output_tokens":0,"total_tokens":0}\n', 0, {"status": "valid", "record_count": 1, "mismatch_lines": []}),
        ("mismatch", '{"id":"b","input_tokens":1,"output_tokens":2,"total_tokens":4}\n', 1, {"status": "total_mismatch", "record_count": 1, "mismatch_lines": [1]}),
        ("invalid", '{"id":"secret","input_tokens":true,"output_tokens":0,"total_tokens":1}\n', 2, {"status": "invalid_input"}),
    ]
    for label, data, expected_code, expected in cases:
        fixture = root / f".acceptance-{label}.jsonl"
        try:
            fixture.write_text(data, encoding="utf-8", newline="")
            result = subprocess.run([str(console), str(fixture)], capture_output=True, text=True, env=env, cwd=outside, check=False)
            assert result.returncode == expected_code, (label, result.returncode)
            assert json.loads(result.stdout) == expected, (label, result.stdout)
            if label == "invalid":
                assert result.stderr == ""
                assert "secret" not in result.stdout
        finally:
            fixture.unlink(missing_ok=True)
    help_result = subprocess.run([str(console), "--help"], capture_output=True, text=True, env=env, cwd=outside, check=False)
    assert help_result.returncode == 0 and "usage:" in help_result.stdout and help_result.stderr == ""
    print("installed acceptance: PASS (version, external import, console script, valid/mismatch/invalid/help, privacy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
