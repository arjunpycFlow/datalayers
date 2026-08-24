# Implementation Plan: Bronze Layer — `data_loader` CLI

**Track ID:** bronze-layer_20260823
**Spec:** [spec.md](./spec.md)
**Created:** 2026-08-23
**Status:** [x] Complete

## Overview

Build `data_loader` phase by phase, TDD where it adds value (per
`conductor/workflow.md`): write each phase's key test(s) before its implementation,
verify, commit, then move to the next phase. Full technical detail for every task below
lives in `scratch_pad.md` — this plan is the tracked checklist; that file is the
reference to consult while implementing.

## Phase 1: Scaffolding

CLI skeleton, storage root, argument parsing — no parsing logic yet.

### Tasks

- [x] Task 1.1: Create `data_loader/` package (`__init__.py`, `__main__.py`, `cli.py`,
      `models.py` stub).
- [x] Task 1.2: Add `duckdb` to `pyproject.toml` dependencies and a `data-loader`
      script entry point. Add `warehouse/` to `.gitignore`.
- [x] Task 1.3: `cli.py` — positional `batch_id`, `--data-root` (default
      `candidate_bundle/data`), `--out-root` (default `warehouse`). Resolve batch
      folder; exit `1` if missing/empty.
- [x] Task 1.4: Create `warehouse/bronze/{data,quarantine}/` on run.

### Verification

- [x] `uv run data-loader batch_2026_01` creates the directory tree and exits `0`
      (empty summary — no parsing yet).
- [x] `uv run data-loader batch_2026_99` (nonexistent batch) exits `1`.

## Phase 2: VCF header-contract parser

Parse a VCF's `##` lines into a per-file contract (INFO/FORMAT/FILTER declarations +
`CSQ`'s declared sub-field order). Write the test first — it's what proves schema drift
is handled by parsing, not luck.

### Tasks

- [x] Task 2.1 (test first): assert `S-0001.somatic.vcf`'s `CSQ` order is exactly
      `[SYMBOL, Consequence, IMPACT, HGVSc, HGVSp, EXON]` (6 items); assert
      `S-0016.somatic.vcf`'s is the same 6 plus `MANE_SELECT` (7 items).
- [x] Task 2.2: `vcf_headers.py` — parse each `##KEY=<...>` line into `(ID, Number,
      Type, Description)`.
- [x] Task 2.3: Extract `CSQ`'s `Format: A|B|C...` clause into an ordered list.

### Verification

- [x] Task 2.1's tests pass against both real batch files.

## Phase 3: VCF row parser

Parse VCF data lines into rows using Phase 2's contract; route unparseable lines to
quarantine.

### Tasks

- [x] Task 3.1 (test first): parsing `S-0001.somatic.vcf` produces zero quarantined
      rows; a `HOTSPOT` row's `info['HOTSPOT']` is `'true'`, not a crash.
- [x] Task 3.2 (test first): parsing a hand-truncated *test fixture* copy of a valid
      VCF (never the real `S-0020.somatic.vcf` — source is immutable, per
      `AGENTS.md` hard rule 1) quarantines exactly the truncated line and parses
      everything before it.
- [x] Task 3.3: `vcf_rows.py` — split on tab; validate field count ==
      `9 + n_sample_columns`; `.`/`""` → NULL; split `INFO` on `;` then `key=value` on
      `=` (bare key → Flag → `'true'`); split `CSQ` on `|` using the declared order, by
      position.
- [x] Task 3.4: any field-count mismatch (including a truncated final line) → route to
      quarantine with `raw_text`, `reason_code='MALFORMED_VCF_LINE'`; continue to next
      line.

### Verification

- [x] Both Task 3.1 and 3.2 tests pass. Also manually verified against the real
      `batch_2026_02/S-0020.somatic.vcf`: 63 valid rows parsed, exactly 1 line
      quarantined (`MALFORMED_VCF_LINE`, line 101).

## Phase 4: Manifest parser + conflicting-duplicate detection

Parse `sample_manifest.csv`; separate exact-duplicate collapse from unresolvable
conflicting duplicates. Independent of Phase 2/3 — can be built in parallel with them.

### Tasks

- [x] Task 4.1 (test first): parsing batch_2026_01's manifest yields 14 usable sample
      rows (`S-0001`..`S-0015` minus `S-0011`, quarantined for disagreeing
      `tumor_purity`, `57%` vs `0.64`); batch_2026_02's manifest yields rows with
      populated `library_prep`.
- [x] Task 4.2: `manifest.py` — CSV parser (header-driven, so batch 2's extra
      `library_prep` needs zero code change); trim; `""` → NULL.
- [x] Task 4.3: row with wrong field count → quarantine,
      `reason_code='MALFORMED_MANIFEST_ROW'`.
- [x] Task 4.4: group parsed rows by `sample_id` — singletons pass through;
      identical-row groups collapse to one; groups where rows disagree on
      any field → both rows to quarantine, `reason_code='CONFLICTING_DUPLICATE'`,
      `reason_detail` naming the disagreeing column and both values.

### Verification

- [x] Task 4.1's test passes against both real batch manifests. Caught and fixed a bug
      during review: the manifest's own `batch_id` column wasn't captured on parsed
      rows (silently filtered by the field allowlist) — added a field + regression
      test before moving on.

## Phase 5: Join + write

Combine Phase 3 + Phase 4 output into the two Parquet outputs.

### Tasks

- [x] Task 5.1 (test first): `bronze.data` for batch_2026_01 contains `S-0008` as a
      variant-NULL row. **Revised mid-task** (see spec.md's Acceptance Criteria note):
      `S-0011`'s VCF variant rows also land, with manifest columns NULL — its manifest
      rows are quarantined separately (`CONFLICTING_DUPLICATE`), but that doesn't erase
      its otherwise-valid variant calls. Both facts verified by test.
- [x] Task 5.2 (test first): running the same batch twice produces two distinct
      timestamped files per output; the earlier files are untouched (diff them).
- [x] Task 5.3: `join.py` — for each `sample_id` in either source, emit one row per
      variant (manifest columns filled if a match exists, else NULL) or one
      manifest-only row (variant columns NULL) if a manifest row has no parsed VCF rows
      for that `sample_id`.
- [x] Task 5.4: `writer.py` — DuckDB parameterized `INSERT` (typed `CREATE TABLE` +
      `executemany`, not a Python-object replacement scan — those don't accept plain
      lists of dicts) then `COPY ... TO ... (FORMAT parquet, COMPRESSION zstd)` to new,
      timestamped filenames — never overwrite.

### Verification

- [x] Both Task 5.1 and 5.2 tests pass (4/4 in `test_join_and_write.py`). Also
      end-to-end sanity-checked against real `batch_2026_02`: 295 data rows, 1
      quarantine record (the truncated line), `S-0020` contributes 63 rows to data.

## Phase 6: Reconciliation check + run summary

Assert nothing was silently lost; print the run summary; set the exit code.

### Tasks

- [x] Task 6.1 (test first): a deliberately broken build (a record silently dropped
      instead of landing in data or quarantine, test-only) trips exit `2`.
- [x] Task 6.2: `run.py` — **revised during implementation** (see note below): two
      independent conservation checks (manifest-side, VCF-side) rather than one
      combined formula — a join can merge a manifest row and a VCF line into a single
      output row, so a flat `reads == writes` sum across both sources doesn't actually
      balance. Fail → `ReconciliationError`, caught in `cli.py` → exit `2`.
- [x] Task 6.3: on success, print e.g. `batch_2026_01: 795 rows written, 2 quarantined,
      0 exact duplicates collapsed` and exit `0`.

### Verification

- [x] Task 6.1's test passes (`tests/test_run.py`, 4/4).
- [x] The correct implementation exits `0` with counts that reconcile for both real
      batches: `batch_2026_01` → 795 rows written, 2 quarantined; `batch_2026_02` → 295
      rows written, 1 quarantined. Re-running `batch_2026_01` confirmed a second,
      distinct timestamped file — first file untouched.

**Note on Task 6.2's revision:** the original wording (a single combined equation) was
never actually implementable correctly — worked through while writing `run.py`, not
found by a failing test this time, but the same "verify the design before coding it
literally" discipline applied in Phase 5.

## Final Verification

- [x] All acceptance criteria in `spec.md` met (updated where implementation surfaced a
      correction — see the `S-0011` note).
- [x] Tests passing: 20/20 (`uv run pytest`).
- [x] `uv run data-loader batch_2026_01` and `uv run data-loader batch_2026_02` both
      exit `0` with correct, reconciling summaries.
- [x] README note added on what was AI-drafted vs. hand-verified (per `AGENTS.md` §5).
- [x] Ready for review.

---

_Generated by Conductor from `scratch_pad.md`. Tasks will be marked [~] in progress and
[x] complete._
