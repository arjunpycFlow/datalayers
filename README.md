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
> (`conductor/tracks/_archive/bronze-layer_20260823/`, all 6 phases). Verified
> against both real batches: `batch_2026_01` → 795 rows written, 2 quarantined
> (`S-0011`'s conflicting manifest duplicate); `batch_2026_02` → 295 rows written, 1
> quarantined (`S-0020`'s truncated line). Gold is not built yet.

## Running the silver-layer builder

`silver_builder` reads bronze's `data` Parquet output, normalizes types and
vocabulary, and writes a trust-layer schema (patients/samples/variant_calls/batches,
plus a normalization-failure quarantine) to `warehouse/silver.duckdb`:

```bash
uv run silver-builder
```

By default it auto-discovers each batch's latest `data_*.parquet` under
`warehouse/bronze/data/`. To rebuild from a specific bronze run instead:

```bash
uv run silver-builder --data-files warehouse/bronze/data/batch_2026_01/data_<timestamp>.parquet [...]
```

**Exit codes:** `0` success · `1` no bronze data files found · `2` reconciliation
invariant failed (a sample went unaccounted for — a bug, not a data defect).

**What it does that bronze didn't:**
- Normalizes `tumor_purity` and all VCF-native allele-frequency-like fields
  (`VAF`, `MAX_POP_AF`, `GNOMAD_AF_POPMAX`, `CCF`) to `[0,1]` fractions.
- Maps `tissue`/`sequencing_platform`/`library_prep`/`qc_status` to controlled
  vocabularies via `config/crosswalks/*.yaml` — an unmapped value quarantines,
  never guessed at.
- Splits bronze's flat, denormalized rows into grain-correct tables:
  `patients` (one row per patient), `samples` (one row per sample, with a
  `has_variant_data` flag), `variant_calls` (one row per sample × variant).
- Full rebuild every run (`CREATE OR REPLACE TABLE`) — deterministic, no
  incremental-state bugs.

> **Status:** silver layer complete
> (`conductor/tracks/silver-layer_20260823/`, all 6 phases). Verified against real
> bronze output for both batches: 1090 rows in → 20 samples, 1089 variant calls, 0
> silver-level quarantines (the known real-data defects were already handled at
> bronze). Example queries confirmed against real data: `TP53` has 57 variants but
> only 17 distinct patients — the exact denominator trap `n_distinct_patients` exists
> to prevent. Gold is not built yet.

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

**Silver layer — a real data-quality finding, not in the original scope:**
`batch_2026_02`'s `VAF` field turned out to be on a 0–100 scale, `batch_2026_01`'s on
0–1 — confirmed by cross-checking against `AD`/`DP` (`32/57=0.5614` vs. the file's
`VAF=56.14`, exactly ×100), not assumed. Added `normalize_af()`, applied to
`VAF`/`MAX_POP_AF`/`GNOMAD_AF_POPMAX`/`CCF`. **Also self-corrected an error along the
way:** an initial pass also flagged `MAX_POP_AF` outliers, which turned out to be a
bug in my own `grep` regex (it truncated scientific notation like `9.6e-06` to `9.6`)
rather than a real data problem — caught and fixed before it shipped in any doc or
test, not left as a false claim. Both are recorded in detail in
`conductor/tracks/silver-layer_20260823/plan.md` (Phase 4).
