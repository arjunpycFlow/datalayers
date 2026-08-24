# Specification: Silver Layer — `silver_builder` CLI

**Track ID:** silver-layer_20260823
**Type:** Feature
**Created:** 2026-08-23
**Status:** Draft

## Summary

A CLI (`silver_builder`) that reads bronze's already-joined, already-clean `data`
Parquet output, normalizes types and vocabulary, splits the denormalized
one-row-per-variant shape into grain-correct tables (patients, samples,
variant_calls, batches), and writes the result into `warehouse/silver.duckdb` as a
full rebuild each run.

## Context

From `conductor/product.md`: the schema has to serve SQL researchers today and a
natural-language assistant later. Bronze (complete —
`conductor/tracks/_archive/bronze-layer_20260823/`) already joins VCF to manifest and
handles deduplication/quarantine at the structural level; that changes silver's job
from the original `working_contexts/` v2 design — **silver no longer joins or
deduplicates.** Its job is what's left: normalize `tumor_purity`/`collection_date`/
vocabulary fields, split bronze's flat rows into declared-grain tables, and extract
what bronze deliberately deferred (named `gt`/`ad`/`dp`/`vaf` columns, `CSQ_*`
annotation fields). Full design, verified source values, and crosswalk YAML content
are in `../../../../scratch_pad.md` — this spec summarizes it for tracking.

## User Story

As a researcher (or the eventual NL assistant), I want a trust-layer schema where
`tumor_purity` is a real fraction, `tissue` is one of five canonical values, and
`patients`/`samples`/`variant_calls` each have a stated grain — so I can write a query
without first having to guess whether `"63%"` means 63.0 or 0.63, or whether a sample
count is actually a patient count.

## Acceptance Criteria

- [ ] **(Added during Phase 4 — real finding, not in the original scope)**
      `variant_calls.vaf` is a consistent `[0,1]` fraction across both batches.
      `batch_2026_02`'s VAF is natively on a 0–100 scale (confirmed via
      `AD`/`DP`: `32/57=0.5614` vs. file's `VAF=56.14`); `normalize_af()` corrects
      it. Same function applied to `max_pop_af`/`gnomad_af_popmax`/`ccf` for
      consistency, though those are already in-range in both real batches.
- [ ] All 5 raw `tissue` casing variants (`Lung`/`LUNG`/`lung`, `breast`, `Colon`/
      `COLON`, `Stomach`/`STOMACH`, `pancreas`/`Pancreas`) map to one of 5 canonical
      values; a genuinely unmapped value quarantines, never guessed at.
- [ ] `tumor_purity` normalizes to a `[0,1]` fraction (`"63%"` → `0.63`); a value that
      would fall outside `[0,1]` after conversion is quarantined, not silently kept as
      a nonsense value like `63.0`.
- [ ] `S-0007`'s `sex_reported=Female` / `sex_inferred=M` normalize independently to
      `F`/`M` and produce `sex_concordant=false` — never silently reconciled to one
      value.
- [ ] `silver.patients` shows `P-0003` with `n_samples=2` — proving patient is a real
      grain above sample, not inferred by accident.
- [ ] `S-0008` (bronze's variant-NULL row) appears in `silver.samples` with
      `has_variant_data=false`, not silently dropped or misrepresented as a normal
      sample.
- [ ] `silver.variant_calls` extracts `gt`/`ad`/`dp`/`vaf` by matching bronze's
      `format_keys` **by name**, not position — verified with a deliberately reordered
      `format_keys` test case.
- [ ] `mane_select`/`ccf`/`gnomad_af_popmax` are `NULL` for batch-1 rows and populated
      for batch-2 rows — additive schema evolution holds at the silver layer too.
- [ ] `--data-files` accepts explicit bronze Parquet paths, overriding
      auto-discovery-of-latest-per-batch entirely.
- [ ] Re-running `silver_builder` against the same bronze inputs produces identical
      `warehouse/silver.duckdb` table **contents** (deterministic full rebuild) —
      verified by row counts/content, not raw file bytes (a DuckDB file can carry
      non-deterministic internal metadata even with identical logical content).
- [ ] The brief's two required example query shapes (join variant→sample metadata;
      aggregate variant count per gene with `n_distinct_patients`, not just
      `n_variants`) run successfully against the real two-batch silver output.

## Dependencies

Bronze layer (`bronze-layer_20260823`, complete) — `silver_builder` reads its
`warehouse/bronze/data/<batch_id>/*.parquet` output. No other dependencies.

## Out of Scope

- Re-joining VCF to manifest, or re-deduplicating manifest rows — bronze's job, done.
- Re-parsing raw VCF/CSV — silver reads bronze's already-structured output only.
- Gold-layer concerns: purpose-scoped completeness contracts, de-identification tiers,
  access-controlled marts.
- Hand-authoring an exhaustive vocabulary taxonomy beyond what's actually observed in
  the two real batches — an unmapped value quarantines rather than blocking the run,
  so the crosswalks don't need to anticipate every hypothetical future value.

## Technical Notes

Full detail (schemas, CLI contract, crosswalk YAML content, module layout, verified
source values re-checked directly against both the raw manifest CSVs and the actual
`bronze.data` Parquet output) is in `../../../../scratch_pad.md`. Key resolved decisions
carried into the plan:

1. **No join, no dedup** — bronze already did both; silver normalizes and splits only.
2. **Grain declared per table** — patients (patient), samples (sample), variant_calls
   (sample × variant). `has_variant_data` on `silver.samples` makes the "no VCF"
   case an explicit fact instead of an inferred NULL pattern.
3. **Vocabulary mapping is config** (`config/crosswalks/*.yaml`, version-controlled),
   never runtime inference — unmapped → quarantine, never guessed.
4. **`tumor_purity` out-of-range is quarantine-worthy**, distinct from merely-missing
   (which stays `NULL`) — the specific guard against the `"63%"`→`63.0` bug.
5. **`collection_date` unparseable → `NULL` + flag**, not quarantine — value-level
   defect, not record-level.
6. **Full rebuild every run** (`CREATE OR REPLACE TABLE`) — deliberate asymmetry with
   bronze (which keeps every run's file): bronze is the audit trail, silver is
   current-best-understanding.
7. **Bronze already trims whitespace** (`manifest.py::_clean()`, confirmed against the
   real `bronze.data` output) — silver's crosswalks only need to handle casing.
8. Stack: Python 3.14, `duckdb` (same dependency bronze already uses), YAML for
   crosswalks (needs a parser — `PyYAML` or stdlib-adjacent; confirm choice in Phase 2).

---

_Generated by Conductor from `scratch_pad.md`. Review and edit as needed._
