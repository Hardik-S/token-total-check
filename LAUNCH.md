# Quick start

Use Python 3.10 or newer. From this repository root, create a virtual environment and install the package as a regular wheel (not editable):

```console
python -m venv .venv
python -m pip install .
token-total-check examples/USAGE.jsonl
```

The example intentionally contains one arithmetic mismatch and exits with status 1. A valid file exits 0, a mismatch exits 1, and invalid input or invocation exits 2. Results are JSON on standard output. Invalid input prints only `{"status":"invalid_input"}` and does not write diagnostics to standard error.

To run the full test suite after installation:

```console
python -m unittest discover -s tests -v
```
