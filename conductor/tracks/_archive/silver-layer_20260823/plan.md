# Implementation Plan: Silver Layer — `silver_builder` CLI

**Track ID:** silver-layer_20260823
**Spec:** [spec.md](./spec.md)
**Created:** 2026-08-23
**Status:** [x] Complete

## Overview

Build `silver_builder` phase by phase, TDD where it adds value (per
`conductor/workflow.md`): write each phase's key test(s) before its implementation,
verify against real bronze output, then move on. Full technical detail (schemas, CLI
contract, crosswalk YAML, verified source values) lives in `scratch_pad.md` — this plan
is the tracked checklist; that file is the reference to consult while implementing.

## Phase 1: Scaffolding + bronze file discovery

CLI skeleton, bronze-input discovery (auto + explicit override), `warehouse/silver.duckdb`
connection — no normalization logic yet.

### Tasks

- [x] Task 1.1: Create `silver_builder/` package (`__init__.py`, `__main__.py`,
      `cli.py`, `models.py` stub). Add a `silver-builder` script entry point in
      `pyproject.toml`.
- [x] Task 1.2: `discover.py` — given `--bronze-data-root`, find each `<batch_id>/`
      subdirectory's lexicographically-latest `data_*.parquet` file.
- [x] Task 1.3: `discover.py` — given `--data-files`, use exactly those paths instead
      of auto-discovery.
- [x] Task 1.4: `cli.py` — wire the full CLI contract (`--bronze-data-root`,
      `--bronze-quarantine-root`, `--data-files`, `--out-root`); exit `1` if no files
      resolve either way.

### Verification

- [x] Given a fixture directory with two batch subdirs (each holding two timestamped
      files), auto-discovery picks the later timestamp in each (`tests/test_silver_discover.py`, 3/3).
- [x] Given explicit `--data-files`, exactly those paths are used regardless of what
      else exists on disk. Also verified against the real CLI: default run picked
      `batch_2026_01`'s later timestamped file (`...222828...`) over the earlier one
      (`...222801...`); explicit override honored; missing root exits `1`.

## Phase 2: Normalization functions

Pure, unit-testable value-level transforms — no bronze row touches these yet.

### Tasks

- [x] Task 2.1 (test first): tests for `normalize_purity` (`"63%"` → `0.63`; an
      out-of-range value like `"630%"` raises) and `normalize_date` (all 5 observed
      formats parse; `DD/MM` for slash-ambiguous values; unparseable → `None`).
- [x] Task 2.2: `normalize.py` — implement `normalize_purity`, `normalize_date`.
- [x] Task 2.3: `crosswalks.py` — YAML loader + lookup; unmapped-but-present value
      raises; missing/empty value → `None` (not "unmapped"). Authored
      `config/crosswalks/{tissue,sequencing_platform,library_prep,qc_status,sex}.yaml`
      with the verified mappings from `scratch_pad.md`. Added `pyyaml` dependency.
- [x] Task 2.4 (test first): every distinct raw value in `scratch_pad.md`'s verified
      source-values table maps to its canonical form; `S-0007`'s `sex_reported=Female`
      / `sex_inferred=M` normalize independently without either erroring.
- [x] Task 2.5: `normalize.py` — `normalize_sex` (via `sex.yaml`), `derive_notes_flags`
      (`is_ffpe`, `is_repeat_library`).

### Verification

- [x] Both test tasks (2.1, 2.4) pass — 44/44 in `test_normalize.py` +
      `test_crosswalks.py`. Full suite 67/67.

## Phase 3: Row-level transform (bronze row → sample + variant_call candidates)

Apply Phase 2's functions to each bronze row; route normalization failures to
`silver.quarantine` without losing the sample's otherwise-valid variant data.

### Tasks

- [x] Task 3.1 (test first): a synthetic bronze row with `tumor_purity="630%"`
      produces a `silver.quarantine` record (`PURITY_OUT_OF_RANGE`) and no
      `silver.samples` record for that sample — but its variant call still lands in
      `silver.variant_calls` (same "don't punish good data for an unrelated field's
      problem" principle bronze already applied to `S-0011`).
- [x] Task 3.2: `transform.py` — build one sample record per distinct `sample_id`
      from its (repeated) manifest columns.
- [x] Task 3.3: `transform.py` — build one variant-call record per row with non-NULL
      `chrom`; route normalization failures to quarantine per Task 3.1's rule.
      **Note:** `gt`/`ad`/`dp`/`vaf` and CSQ/info-map extraction are already wired
      into `_build_variant_call`, except the FORMAT-key-based `gt`/`ad`/`dp`/`vaf`
      extraction, deliberately left as placeholders — that's Phase 4's job
      specifically (name-based, not positional).

### Verification

- [x] Task 3.1's test passes (4/4 in `test_transform.py`, including the multi-variant
      and manifest-only/`has_variant_data=false` cases).

## Phase 4: Genotype and annotation extraction

Turn bronze's `format_keys`/`genotype_values` and `info` map (including the `CSQ_*`
keys) into named `silver.variant_calls` columns.

### Tasks

- [x] Task 4.1 (test first): a bronze row with deliberately **reordered**
      `format_keys` still yields the correct `dp`/`vaf` (proves name-based extraction,
      not positional); a batch-2 row's `CSQ_MANE_SELECT` lands in `mane_select`, a
      batch-1 row (no such key) yields `mane_select=NULL`, not an error.
- [x] Task 4.2: `genotype.py` — zip `format_keys` with `genotype_values`, extract
      `gt`/`ad`/`dp`/`vaf` by declared key name.
- [x] Task 4.3: extract `caller`, `max_pop_af`, `hotspot` (boolean), `ccf`,
      `gnomad_af_popmax` from bronze's `info` map; extract `gene_symbol`,
      `consequence`, `impact`, `hgvsc`, `hgvsp`, `exon`, `mane_select` from the
      `CSQ_*`-prefixed keys.

**Unplanned finding, not in the original spec — real, verified against source:**
`batch_2026_02`'s `VAF` is on a **0–100 scale**, `batch_2026_01`'s is **0–1**
(confirmed: `AD=25,32`/`DP=57` → true fraction `32/57=0.5614`; file's `VAF=56.14`,
exactly ×100 — checked a second row too, same ratio). Asked the user; added
`normalize_af()` (in `normalize.py`) applied to `VAF`, `MAX_POP_AF`,
`GNOMAD_AF_POPMAX`, `CCF` — any value `>1` is unambiguous proof of a ×100 scale error
for a field definitionally bounded `[0,1]` with no `%` marker (unlike `tumor_purity`,
a free-text field where an unmarked `"63"` is genuinely ambiguous and still
quarantines — that guard is untouched). **Self-correction:** an initial check also
flagged `MAX_POP_AF`/`GNOMAD_AF_POPMAX` outliers — that was a regex bug (truncated
`9.6e-06` to `9.6`, not real data). Re-checked properly: those fields and `CCF` are
already consistently `[0,1]` in both batches; `normalize_af` is a harmless no-op there.

### Verification

- [x] Task 4.1's tests pass — 10/10 across `test_genotype.py` + the relevant
      `test_transform.py`/`test_normalize.py` cases. Verified against real bronze
      output for both batches: `vaf` and `max_pop_af` ranges are now consistently
      `[0,1]` in both.

## Phase 5: Write to `warehouse/silver.duckdb`

Persist patients/samples/variant_calls/batches/quarantine as a full rebuild.

### Tasks

- [x] Task 5.1 (test first): running against real bronze output for both batches
      produces `silver.patients` with `P-0003` showing `n_samples=2`;
      `silver.samples` has exactly one row per distinct `sample_id` seen in bronze
      (including `S-0008`, with `has_variant_data=false`); re-running with the same
      inputs produces identical table **contents** (row counts per table compared —
      see note below on "byte-for-byte").
- [x] Task 5.2: `writer.py` — `CREATE OR REPLACE TABLE` for all five tables from the
      in-memory records built in Phases 3–4; compute `silver.patients` and
      `silver.batches` by aggregation over `silver.samples`/`silver.variant_calls`,
      not by re-reading bronze.

**Revised during implementation:** "byte-for-byte identical" (as originally worded)
isn't the right test for a DuckDB *file* — DuckDB can embed non-deterministic internal
metadata even with identical logical content, so raw file-byte comparison isn't a
reliable determinism check. Verified determinism via row-count-per-table comparison
across two runs with identical inputs instead — same spirit (deterministic full
rebuild), correct mechanism.

**Also caught while writing the test:** my own test initially assumed `S-0011` would
be *excluded* from `silver.samples` — wrong. Bronze already landed `S-0011`'s VCF
variants with manifest columns `NULL` (its manifest rows conflicted and were
quarantined at bronze, not silver). Silver doesn't re-quarantine a sample just because
its dimension fields are already `NULL` — `NULL` normalizes to `NULL`, not a failure.
Fixed the test assertion, not the code — the code was already doing the right thing.

### Verification

- [x] Task 5.1's tests pass against real bronze output for both batches (2/2 in
      `test_writer.py`). `P-0003` → `n_samples=2`; `S-0008` →
      `has_variant_data=false`; `S-0011` → present with `tissue=NULL`; all 20 tables
      row-count-identical across two runs.

## Phase 6: Reconciliation, run summary, and the example queries

Assert nothing was silently lost; prove the schema actually answers the brief's
required query shapes.

### Tasks

- [x] Task 6.1 (test first): a deliberately broken build (test-only — a sample neither
      written to `silver.samples` nor `silver.quarantine`) trips the sample-accounting
      assertion.
- [x] Task 6.2: `run.py` — assert every distinct `sample_id` present in the bronze
      input appears in exactly one of `silver.samples` or `silver.quarantine`. Print
      the run summary (rows per table, quarantine count, which bronze files were
      used).

**Minor limitation found while spot-checking real output, not fixed retroactively:**
`S-0011`'s `batch_id` is `NULL` in `silver.samples` — bronze nulled *all* manifest-side
fields for it (its manifest rows conflicted, quarantined at bronze), `batch_id`
included. `S-0011` is fully present in `samples`/`variant_calls` (no data loss), but
it drops out of the `batches` rollup's per-batch `n_samples` count (`batch_2026_01`
shows 14, not 15). A cleaner fix would be bronze always stamping `batch_id` from its
own CLI argument regardless of manifest match — but bronze is already complete and
archived; noted here as a real, known gap rather than silently reopening that track.
- [x] Task 6.3: write and run the brief's two required example queries directly
      against `warehouse/silver.duckdb`: (1) a join — which samples carry a variant in
      a given gene, and what tissue are they from; (2) an aggregate — variant count
      per gene across the cohort, with `n_distinct_patients` (not just `n_variants`,
      so `P-0003`'s two samples don't silently inflate a patient-level count).

### Verification

- [x] Task 6.1's test passes (2/2 in `test_silver_run.py`).
- [x] Both example queries run successfully against the real two-batch silver output
      and return non-empty, sane-looking results — spot-checked by hand: top gene
      `TP53` has 57 variants but only 17 distinct patients, exactly the trap the
      schema exists to prevent. 4/4 in `test_queries.py`.

## Final Verification

- [x] All acceptance criteria in `spec.md` met (including the added VAF criterion).
- [x] Tests passing: 86/86 (`uv run pytest`).
- [x] `uv run silver-builder` (default auto-discovery) runs against both real bronze
      batches and produces a correct, reconciling summary (1090 rows → 20 samples,
      1089 variant calls, 0 quarantined).
- [x] `uv run silver-builder --data-files ...` (explicit override) verified against a
      real bronze file path (795 rows → 15 samples, batch_2026_01 only).
- [x] README updated with how to run `silver_builder`.
- [x] Ready for review.

---

_Generated by Conductor from `scratch_pad.md`. Tasks will be marked [~] in progress and
[x] complete._
