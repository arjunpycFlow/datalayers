# Tech Stack — inocras_datalayers

## Languages

- **Python 3.14** — `pyproject.toml` (`requires-python = ">=3.14"`), pinned via
  `.python-version`.

## Frontend

None — CLI only.

## Backend

None — a CLI (`data_loader`), stdlib `argparse` for the interface. No web framework.

## Database / storage

- **DuckDB** — query engine for silver (`warehouse/silver.duckdb`) and gold
  (`warehouse/gold.duckdb`); also writes bronze's Parquet output via `COPY ... TO`.
- **Parquet-on-disk** — bronze layer (`warehouse/bronze/{data,quarantine}/<batch_id>/`).

Resolved decision (D1 in `../working_contexts/`) — no SQLite, no server-based database.

## Key dependencies

- `duckdb` — the only production dependency. VCF and CSV parsing use the stdlib
  (`csv`, plain text) deliberately — no dependency the author hasn't used, per the
  pairing-session working agreement.
- `pytest` (dev only, `[dependency-groups].dev`) — added during the bronze-layer track
  for the phase-by-phase TDD tests. Not a runtime dependency.

## Infrastructure

Local only. No cloud accounts, no managed services, nothing to provision — the reviewer
clones the repo and runs one documented command (hard rule 2, `../AGENTS.md` §3).

## Detected vs. resolved

This was a brownfield setup: `pyproject.toml` existed with no dependencies declared yet
and no frameworks in use. Everything above beyond "Python 3.14" reflects decisions
already resolved in `../working_contexts/` (the highest-version file there is
authoritative if this drifts).
