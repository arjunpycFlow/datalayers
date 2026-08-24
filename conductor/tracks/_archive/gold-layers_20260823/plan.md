# Implementation Plan: Gold Layer — `gold_builder` CLI

**Track ID:** gold-layers_20260823
**Spec:** [spec.md](./spec.md)
**Created:** 2026-08-23
**Status:** [x] Complete

## Overview

Build `gold_builder` phase by phase, TDD where it adds value (per
`conductor/workflow.md`): write each phase's key test(s) before its implementation,
verify against real silver output, then move on — no per-phase approval stop, no
auto-commit (both per standing instruction). Full technical detail (contract YAML
shape, exact column tiers per mart, the verified real-data numbers) lives in
`scratch_pad.md` — this plan is the tracked checklist.

## Phase 1: Scaffolding + contract loading

`gold_builder/` package skeleton; load `config/gold_contracts/*.yaml` into a typed
contract object.

### Tasks

- [x] Task 1.1: Create `gold_builder/` package (`__init__.py`, `__main__.py`,
      `cli.py`, `models.py` stub). Add a `gold-builder` script entry point in
      `pyproject.toml`.
- [x] Task 1.2: `contracts.py` — load a `config/gold_contracts/*.yaml` file into a
      typed contract object (mart name, schema/tier, grain, purpose, the 4
      column-tier lists, filters).
- [x] Task 1.3: Authored `config/gold_contracts/{gold_variant_gene_lookup_v1,
      gold_cohort_gene_burden_v1, gold_sample_clinical_profile_v1}.yaml` per the
      column tiers in `scratch_pad.md` §"Marts".
- [x] Task 1.4: Validate at load time — a column listed in more than one tier, or an
      unknown tier name, raises immediately (not silently accepted).

### Verification

- [x] Loading `gold_variant_gene_lookup_v1.yaml` yields the exact
      mandatory/good_to_have/okay_to_have/not_relevant lists from `scratch_pad.md`
      (3/3 in `test_gold_contracts.py`). All three real contracts spot-checked to
      parse correctly, including `not_relevant`'s inline YAML comments.
- [x] A malformed contract (duplicate column across tiers, unknown tier name) raises
      at load time.

## Phase 2: Row-level contract application (mart 1 — the join requirement)

Build `gold_open.gold_variant_gene_lookup_v1`: given a contract and a
`silver.variant_calls` ⋈ `silver.samples` row, decide include (contract's columns
only, `not_relevant` ones dropped) or exclude-and-quarantine.

### Tasks

- [x] Task 2.1 (test first): a synthetic row missing a `mandatory` column quarantines
      with the correct `missing_columns` list; a row missing only a
      `good_to_have`/`okay_to_have` column still lands, field `NULL`; a row's
      `not_relevant` columns don't appear in the output row's shape at all.
- [x] Task 2.2: `apply.py` (generic, reusable across row-level marts) +
      `marts/variant_gene_lookup.py` (this mart's source query) — apply the contract
      row-by-row over the joined silver data; route failures to a
      `GoldQuarantineRecord` with `exclusion_reason_code`, `exclusion_detail`,
      `missing_columns`.
- [x] Task 2.3 (test first, against real data): `S-0011`'s rows quarantine for this
      mart specifically (`MISSING_MANDATORY_COLUMN` on `tissue`) — confirmed all 57
      of its variant rows quarantine here while remaining fully present in silver.

### Verification

- [x] Both test tasks (2.1, 2.3) pass — 5/5 in `test_gold_apply.py`, including a
      full end-to-end real-data run: `rows + quarantine == n_variant_calls` (nothing
      lost), `TP53` rows present with exactly the contract's columns,
      `collection_date` confirmed absent (not just NULL).
- [x] Querying the built rows by `gene_symbol` returns `sample_id` + `tissue`/
      `diagnosis` — the brief's join question, directly answerable.

## Phase 3: Aggregate mart (mart 2 — the aggregate requirement)

Build `gold_open.gold_cohort_gene_burden_v1` by grouping the same joined view on
`gene_symbol`.

### Tasks

- [x] Task 3.1: `marts/cohort_gene_burden.py` — compute `n_variants`,
      `COUNT(DISTINCT sample_id)` as `n_distinct_samples`,
      `COUNT(DISTINCT patient_id)` as `n_distinct_patients`, and
      `COUNT(DISTINCT CASE WHEN patient_id IS NULL THEN sample_id END)` as
      `n_samples_with_unknown_patient` — never a bare `count`, and never
      `COUNT(DISTINCT patient_id)` reported alone (it silently drops `NULL`
      patients — confirmed this is exactly `S-0011`'s situation).
- [x] Task 3.2: contributing-row quarantine — a `variant_calls` row with
      `gene_symbol IS NULL` can't contribute to any gene's count; routed to a
      `GoldQuarantineRecord` (`MISSING_GENE_SYMBOL`). Real data has 0 such rows
      (confirmed), so tested with a synthetic in-memory DuckDB fixture instead.
- [x] Task 3.3 (test first, against real data): `TP53` → `n_variants=57`,
      `n_distinct_samples=19`, `n_distinct_patients=17`,
      `n_samples_with_unknown_patient=1` — all four confirmed exactly. Confirmed
      `n_variants` **with** `S-0011` (57) differs from **without** it (54, diff of
      3) — its variants are really counted — while `n_distinct_patients` correctly
      excludes it and `n_samples_with_unknown_patient=1` is where the gap surfaces.

### Verification

- [x] Task 3.3's test passes against real data — 3/3 in
      `test_gold_cohort_gene_burden.py`, including the synthetic quarantine test.
- [x] No column anywhere in this mart is literally named `count` (asserted directly
      in the test).

## Phase 4: Restricted mart (mart 3) + schema/access separation

Build `gold_restricted.gold_sample_clinical_profile_v1`, full fidelity, sample grain.

### Tasks

- [x] Task 4.1: `marts/sample_clinical_profile.py` — apply the mart-3 contract over
      `silver.samples` directly (no variant join — sample grain only).
- [x] Task 4.2: `writer.py` — `CREATE SCHEMA IF NOT EXISTS` per mart's declared
      schema; write both the mart table and its `_quarantine` sibling (naming fixed
      up so `_quarantine` lands before the version suffix, e.g.
      `gold_sample_clinical_profile_quarantine_v1`).
- [x] Task 4.3 (test first): `gold_sample_clinical_profile_v1`'s `collection_date`/
      `tumor_purity` confirmed exact against real silver values for every row — no
      banding/generalisation applied (none of the three marts currently need a
      banded/generalised date or purity — the two `gold_open` marts drop those
      fields entirely rather than generalise them, which is the stronger
      minimization choice; a banding function can be added if a future open mart
      needs one, none does yet).

### Verification

- [x] Task 4.3's test passes — 2/2 in `test_gold_writer.py`.
- [x] Confirmed: `gold_restricted` schema created, `gold_sample_clinical_profile_v1`
      and its quarantine table both present with correct row counts.
- [x] **Documented, not just built:** `writer.py`'s `write_mart` docstring states
      plainly that the schema split is structural only — `GRANT` confirmed
      unsupported in embedded DuckDB; real enforcement is the S3/IAM mapping in
      `working_contexts/` v2 §6.3.

## Phase 5: Reconciliation + `not_relevant` schema verification + CLI

### Tasks

- [x] Task 5.1 (test first): a deliberately broken build (test-only — a row dropped
      from both a mart and its quarantine sibling) trips the reconciliation
      assertion.
- [x] Task 5.2: `run.py` — per-mart reconciliation: row-level marts assert
      `n_source_rows == len(rows) + len(quarantine)`; the aggregate mart asserts
      `n_source_rows == sum(n_variants) + len(quarantine)`. Fail → `ReconciliationError`.
- [x] Task 5.3 (test first): confirmed `not_relevant` column leaks are caught —
      writer respects the contract by construction (0 leaks on a real write), and a
      simulated leak (`ALTER TABLE ... ADD COLUMN`) is correctly detected by
      `_check_not_relevant_absent`, proving the check itself works, not just that
      nothing happens to trigger it.
- [x] Task 5.4: `cli.py` — wired `--silver-db`, `--out-root`, `--mart NAME ...`; exit
      `0`/`1`/`2` per the spec's exit codes.

### Verification

- [x] Both test tasks (5.1, 5.3) pass — 5/5 in `test_gold_run.py`, including a full
      3-mart run against real silver output.
- [x] `uv run gold-builder` (all marts, default) runs against real silver output:
      `gold_cohort_gene_burden_v1` → 36 rows, 0 quarantined;
      `gold_sample_clinical_profile_v1` → 17 rows, 3 quarantined (`S-0003` missing
      `tumor_purity`, `S-0011` fully NULL, `S-0012` missing `collection_date` — all
      three previously-known real gaps, not new surprises);
      `gold_variant_gene_lookup_v1` → 1032 rows, 57 quarantined (all `S-0011`).
      `--mart gold_variant_gene_lookup_v1` (single-mart filter) and a missing
      `--silver-db` (exit `1`) both verified.

## Phase 6: Determinism + governance documentation

### Tasks

- [x] Task 6.1 (test first): re-running `gold_builder` against unchanged silver
      output produces identical row counts/content across all three marts and their
      quarantine siblings (content-comparison, not raw file bytes — same caveat as
      silver's Phase 5).
- [x] Task 6.2: wrote the governance note into the submission README — the
      de-identification-per-tier reasoning, the explicit "access is the control, not
      anonymisation" limitation (`working_contexts/` v1 §4 / v2 §6.2), the `GRANT`
      caveat, and what an AI assistant needs — per the brief's required
      *"Governance note"* section. Also fixed two stale archived-track path
      references in the README, noticed along the way.

### Verification

- [x] Task 6.1's test passes — `test_gold_determinism.py`: two independent runs
      against real silver output produce identical table-content counts across
      every table in `gold.duckdb`.
- [x] Governance note present in the README, states the k-anonymity limitation
      explicitly rather than implying gold-tier de-identification solves
      re-identification risk.

## Final Verification

- [x] All acceptance criteria in `spec.md` met.
- [x] Tests passing: 105/105 (`uv run pytest`).
- [x] `uv run gold-builder` runs against real silver output and produces correct,
      reconciling summaries for all three marts.
- [x] `uv run gold-builder --mart gold_variant_gene_lookup_v1` (single-mart filter)
      verified to work.
- [x] README updated: how to run `gold_builder`, plus the governance note.
- [x] Ready for review.

---

_Generated by Conductor from `scratch_pad.md`. Tasks will be marked [~] in progress and
[x] complete._
