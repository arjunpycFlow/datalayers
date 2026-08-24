# Python Style Guide

Python conventions following PEP 8 and modern best practices.

**Project-specific override:** this repo's working agreement (`../../AGENTS.md` §5) is
*"comprehensibility beats cleverness — no metaprogramming, no dense one-liners, no
framework the author hasn't used. If it can't be explained aloud in thirty seconds,
it's the wrong implementation."* That takes precedence over any pattern below that
conflicts with it. In practice: prefer the plain patterns (dataclasses, context
managers, straightforward exception handling) over the advanced ones (custom
decorators, `ParamSpec`/generic `Protocol` typing, retry-with-backoff abstractions)
unless a specific task genuinely needs them.

## PEP 8 Fundamentals

### Naming Conventions

```python
# Variables and functions: snake_case
user_name = "John"
def calculate_total(items):
    pass

# Constants: SCREAMING_SNAKE_CASE
MAX_CONNECTIONS = 100
DEFAULT_TIMEOUT = 30

# Classes: PascalCase
class UserAccount:
    pass

# Private: single underscore prefix
class User:
    def __init__(self):
        self._internal_state = {}

# Module-level "private": single underscore
_module_cache = {}
```

### Indentation and Line Length

```python
# 4 spaces per indentation level
def function():
    if condition:
        do_something()

# Line length: 88 characters (Black) or 79 (PEP 8)
result = some_function(
    argument_one,
    argument_two,
    argument_three,
)
```

### Imports

```python
# Standard library
import csv
from pathlib import Path

# Third-party
import duckdb

# Local application
from data_loader.models import DataRow, QuarantineRow

# Avoid wildcard imports
# Bad: from module import *
# Good: from module import specific_item
```

## Type Hints

Use plain, direct type hints — this project's parsing code deals in simple shapes
(strings, dicts, lists of dataclasses), not generics or structural typing.

```python
from typing import Optional

def parse_info_field(raw: str) -> dict[str, str]:
    """Parse a VCF INFO field into a key→value map."""
    ...

def find_manifest_row(sample_id: str) -> Optional[dict]:
    ...
```

### Dataclasses (preferred over ad-hoc dicts/tuples for structured records)

```python
from dataclasses import dataclass, field

@dataclass
class QuarantineRow:
    batch_id: str
    entity_type: str
    source_file: str
    source_line_no: int
    raw_text: str
    reason_code: str
    reason_detail: str
    run_id: str
    run_timestamp: str
```

## Docstrings

One-line docstrings for straightforward functions; multi-line only when a non-obvious
constraint or invariant needs explaining (matches the project's general no-comments
default — see `../../CLAUDE.md`).

```python
def parse_csq(raw: str, field_order: list[str]) -> dict[str, str]:
    """Split a CSQ value by its file-declared sub-field order."""
    return dict(zip(field_order, raw.split("|")))
```

## Virtual Environments

This project uses `uv`:

```bash
uv venv
uv sync
uv run data-loader batch_2026_01
```

### Project structure (this repo)

```
inocras_datalayers/
├── data_loader/          # the CLI package
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── vcf_headers.py
│   ├── vcf_rows.py
│   ├── manifest.py
│   ├── join.py
│   ├── writer.py
│   ├── run.py
│   └── models.py
├── tests/
├── pyproject.toml
└── warehouse/             # generated output, gitignored
```

## Testing

`pytest`, per the working context's testing plan (see `../../scratch_pad.md` §9 for the
bronze-layer test list — `TB-1` through `TB-7`).

```python
import pytest
from data_loader.vcf_headers import parse_csq_field_order

def test_csq_field_order_batch_1():
    order = parse_csq_field_order(BATCH_1_CSQ_DESCRIPTION)
    assert order == ["SYMBOL", "Consequence", "IMPACT", "HGVSc", "HGVSp", "EXON"]

def test_csq_field_order_batch_2_has_mane_select():
    order = parse_csq_field_order(BATCH_2_CSQ_DESCRIPTION)
    assert order == ["SYMBOL", "Consequence", "IMPACT", "HGVSc", "HGVSp", "EXON", "MANE_SELECT"]
```

Fixtures for shared setup (e.g. loading a sample VCF header) are fine; mocking is
unlikely to be needed — this project reads real local files, not network services.

## Error Handling

Prefer the project's own quarantine mechanism over exceptions for *data* problems — a
malformed line is not a Python exception, it's a quarantine record (see
`../../scratch_pad.md` §3.3). Reserve real exceptions for genuine bugs: a batch folder
that doesn't exist, a reconciliation invariant that fails.

```python
class BatchNotFoundError(Exception):
    """Raised when the requested batch folder doesn't exist."""

class ReconciliationError(Exception):
    """Raised when rows_read != rows_written + rows_quarantined + rows_deduped."""
```

## Code Quality Tools

### Ruff

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
target-version = "py314"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501"]  # line length handled by the formatter

[tool.ruff.lint.isort]
known-first-party = ["data_loader"]
```

### mypy (optional — use where types clarify a non-obvious shape)

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.14"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

Not set to `strict = true` by default — matches the "flexible, add where it makes
sense" workflow policy (`../workflow.md`) rather than mandating full typing coverage.
