"""Strict JSONL validation and normalized token-total arithmetic."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MAX_COMPONENT = 1_000_000_000_000
MAX_TOTAL = 2_000_000_000_000
FIELDS = {"id", "input_tokens", "output_tokens", "total_tokens"}


class InvalidInput(Exception):
    """An input file does not satisfy the documented fixture schema."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInput
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise InvalidInput


def _check_unicode(value: Any) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise InvalidInput
    elif isinstance(value, list):
        for item in value:
            _check_unicode(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_unicode(key)
            _check_unicode(item)


def _read_records(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", errors="strict", newline="") as stream:
            lines = list(stream)
    except (OSError, UnicodeError, ValueError):
        raise InvalidInput from None

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line in lines:
        raw = line.rstrip("\r\n")
        if not raw.strip():
            raise InvalidInput
        try:
            record = json.loads(
                raw,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            _check_unicode(record)
        except (json.JSONDecodeError, InvalidInput, RecursionError, ValueError):
            raise InvalidInput from None
        if not isinstance(record, dict) or set(record) != FIELDS:
            raise InvalidInput
        identifier = record["id"]
        if not isinstance(identifier, str) or not identifier or identifier in seen_ids:
            raise InvalidInput
        seen_ids.add(identifier)
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = record[field]
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidInput
            limit = MAX_TOTAL if field == "total_tokens" else MAX_COMPONENT
            if not 0 <= value <= limit:
                raise InvalidInput
        records.append(record)
    return records


def evaluate(path: Path) -> tuple[dict[str, Any], int]:
    records = _read_records(path)
    mismatches = [
        line_number
        for line_number, record in enumerate(records, 1)
        if record["total_tokens"] != record["input_tokens"] + record["output_tokens"]
    ]
    status = "total_mismatch" if mismatches else "valid"
    return {"status": status, "record_count": len(records), "mismatch_lines": mismatches}, int(bool(mismatches))


def _help() -> str:
    return (
        "usage: token-total-check [-h] USAGE.jsonl\n\n"
        "Check normalized input_tokens + output_tokens == total_tokens in a JSONL fixture.\n"
        "Reads synthetic data only. This does not validate provider usage or billing.\n"
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["-h"], ["--help"]):
        sys.stdout.write(_help())
        return 0
    if len(args) != 1 or args[0].startswith("-"):
        sys.stdout.write('{"status":"invalid_input"}\n')
        return 2
    try:
        result, status = evaluate(Path(args[0]))
    except InvalidInput:
        sys.stdout.write('{"status":"invalid_input"}\n')
        return 2
    sys.stdout.write(json.dumps(result, separators=(",", ":"), ensure_ascii=True) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
