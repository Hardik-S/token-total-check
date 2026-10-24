# Token Total Check

Token Total Check is a small offline command-line checker for one explicit arithmetic rule in synthetic JSONL fixtures: `input_tokens + output_tokens == total_tokens`.

Install and run it using the [quick start](LAUNCH.md). It requires Python 3.10 or newer and has no runtime dependencies. The example fixture is synthetic and includes a deliberate mismatch so the nonzero mismatch result is visible.

Each JSONL row must contain exactly four fields: `id` (a nonempty unique string), `input_tokens` and `output_tokens` (integers from 0 through 1,000,000,000,000), and `total_tokens` (an integer from 0 through 2,000,000,000,000). Booleans and floating point values are not integers for this schema. Empty files are valid. IDs are compared exactly as Unicode strings, without normalization.

Output is one JSON object. A valid file returns `{"status":"valid","record_count":N,"mismatch_lines":[]}` with exit code 0. Arithmetic discrepancies return `{"status":"total_mismatch","record_count":N,"mismatch_lines":[...]}` with sorted, one-based physical line numbers and exit code 1. Invalid input returns only `{"status":"invalid_input"}` and exit code 2; no IDs, token values, file paths, source text, hashes, or exception details are exposed.

The checker strictly validates UTF-8 JSONL, unique JSON keys and IDs, exact schema, numeric bounds, and Unicode scalar values. It validates the entire file before writing a result. Physical lines are separated by CR, LF, or CRLF; Unicode line separators are not record delimiters.

This tool checks only the normalized arithmetic in each supplied fixture. It does not tokenize text, identify a provider, validate telemetry conventions, or establish actual usage, billing, cost savings, or model quality.
