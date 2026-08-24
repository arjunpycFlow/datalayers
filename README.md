# inocras_datalayers

Genomic data foundation — ingests somatic VCF + sample manifest batches into a
governed, queryable curated zone. See [`AGENTS.md`](AGENTS.md) for the full operating
context and [`working_contexts/`](working_contexts/) (highest version number) for the
current architecture and resolved decisions.

## Setup

```bash
uv sync
```

Requires Python 3.14+ (pinned via `.python-version`). No cloud accounts, no external
services — everything runs locally.

## Running the bronze-layer loader

`data_loader` ingests one batch at a time from `candidate_bundle/data/` into
`warehouse/bronze/`:

```bash
uv run data-loader batch_2026_01
uv run data-loader batch_2026_02
```

Equivalent module form:

```bash
uv run python -m data_loader batch_2026_01
```

Optional flags (defaults shown):

```bash
uv run data-loader batch_2026_01 --data-root candidate_bundle/data --out-root warehouse
```

**Exit codes:** `0` success · `1` batch folder missing or empty · `2` reconciliation
invariant failed (a bug, not a data defect).

**Output:** two Parquet files per run, one per batch, never overwritten —

```
warehouse/bronze/data/<batch_id>/data_<timestamp>.parquet
warehouse/bronze/quarantine/<batch_id>/quarantine_<timestamp>.parquet
```

`data` holds every combinable record (joined variant + manifest, `NULL` where a side
is legitimately missing). `quarantine` holds only records that couldn't be parsed or
safely combined at all (malformed lines, conflicting duplicate manifest rows) — nothing
is ever silently dropped.

> **Status:** bronze layer complete
> (`conductor/tracks/bronze-layer_20260823/`, all 6 phases). Verified against both real
> batches: `batch_2026_01` → 795 rows written, 2 quarantined (`S-0011`'s conflicting
> manifest duplicate); `batch_2026_02` → 295 rows written, 1 quarantined (`S-0020`'s
> truncated line). Silver and gold are not built yet.

## AI assistance note

Built with Claude Code, using the Conductor plugin's spec → phased plan → implement
workflow. Every phase's key claims were verified by running code against the real
batch data, not asserted from the plan alone — e.g. `S-0020`'s truncation was checked
directly against the actual file, not just a test fixture.

**Where a design gap was caught, not just implemented as specified:** Phase 5 testing
found the original spec's claim — that `S-0011` should be entirely absent from
`bronze.data` because its manifest rows conflict — was actually wrong: it would have
silently dropped that sample's independently-valid variant calls over an unrelated
field's ambiguity. Surfaced to the user as a design fork rather than resolved
silently; `S-0011`'s variants now land with manifest columns `NULL`, same as `S-0008`'s
gap. `spec.md`, `plan.md`, and the tests were all corrected to match. Phase 6's
reconciliation formula was similarly revised — the originally-planned single combined
equation didn't actually balance once the join's merge behavior was worked through, so
it became two independent conservation checks instead.
