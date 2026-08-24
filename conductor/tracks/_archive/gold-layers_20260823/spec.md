# Specification: Gold Layer — `gold_builder` CLI

**Track ID:** gold-layers_20260823
**Type:** Feature
**Created:** 2026-08-23
**Status:** Draft

## Summary

A CLI (`gold_builder`) that reads `warehouse/silver.duckdb` and writes
**purpose-scoped marts** to `warehouse/gold.duckdb` — one mart per research question,
each with its own **4-tier** column-relevancy contract (`mandatory` / `good_to_have` /
`okay_to_have` / `not_relevant`), its own de-identification posture (`gold_open` vs.
`gold_restricted`), and its own quarantine sibling. There is no single generic gold
schema — a silver row can be complete for one mart and excluded from another
simultaneously, both facts recorded.

## Context

From `conductor/product.md`: the schema has to serve SQL researchers today and a
future NL assistant. Bronze and silver (both complete —
`conductor/tracks/_archive/`) already join, deduplicate, normalize types, and map
vocabulary; gold's job is purely **purpose-scoping** — deciding, per research
question, which columns matter and how much, and excluding only what genuinely can't
answer that question. Full design (verified against real data, not assumed) is in
`../../../../scratch_pad.md` — this spec summarizes it for tracking.

**This revises `working_contexts/` v2 §5's original gold design in one specific way**
(everything else there — purpose-scoped completeness contracts, the naming
convention, per-mart quarantine, the S3/governance mapping — still stands): v2's
2-tier `required_columns`/`optional_columns` becomes a **4-tier** scheme. See
`scratch_pad.md` §"The 4-tier column model" for the full rationale.

## User Story

As a researcher (or the eventual NL assistant), I want gold marts scoped to specific
questions — not one generic table — so that a column's absence or NULL-tolerance is
always explainable by *why this mart doesn't need it*, and so a record isn't silently
dropped from a mart just because a field irrelevant to that mart's purpose happens to
be missing.

## Acceptance Criteria

- [ ] `gold_open.gold_variant_gene_lookup_v1` answers the brief's join question —
      queryable by `gene_symbol`, returns `sample_id` + `tissue`/`diagnosis`.
- [ ] `gold_open.gold_cohort_gene_burden_v1` answers the brief's aggregate question —
      `TP53` shows `n_variants=57`, `n_distinct_samples=19`, `n_distinct_patients=17`,
      `n_samples_with_unknown_patient=1` (all present, distinctly named — see below).
- [ ] `S-0011` (its `tissue`/`patient_id`/etc. are `NULL` — bronze's own decision, not
      a defect) is **excluded** from mart 1 (`tissue` is `mandatory` there,
      quarantined `MISSING_MANDATORY_COLUMN`); its 3 `TP53` variants **are** counted
      in mart 2's `n_variants` (57, confirmed 54 without it); it is correctly
      **excluded** from `n_distinct_patients` (`patient_id` is `NULL`, and SQL's
      `COUNT(DISTINCT ...)` silently drops `NULL`) and instead surfaces in
      `n_samples_with_unknown_patient=1` — the gap made visible, not hidden.
- [ ] Every mart's `not_relevant` columns are verifiably **absent** from that mart's
      `DESCRIBE` output — not merely NULL.
- [ ] `gold_sample_clinical_profile_v1` lives in schema `gold_restricted`, with exact
      (unbanded, ungeneralised) `collection_date`/`tumor_purity` — `gold_open` marts
      use generalised/banded/absent versions of the same fields.
- [ ] Reconciliation holds per mart: every silver row in that mart's grain lands in
      either the mart or its `_quarantine` sibling, never neither.
- [ ] Re-running `gold_builder` against unchanged silver output produces identical
      mart contents (content-comparison, not raw file bytes — same caveat as silver).

## Dependencies

Silver layer (`silver-layer_20260823`, complete) — `gold_builder` reads
`warehouse/silver.duckdb`. Confirmed present on this branch (`db_gold_cases_v01`,
post-rebase). No other dependencies.

## Out of Scope

- A generic, one-size gold schema reused across marts — explicitly rejected.
- Re-deriving silver's normalization, joins, or dedup.
- Solving k-anonymity by generalisation (already concluded unachievable at n=20 by
  that route, `working_contexts/` v1 §4 / v2 §6.2) — gold's job is column
  minimization + access-tier separation, not a stronger anonymisation algorithm.
- Real, enforced multi-user access control — embedded DuckDB has no `GRANT`/role
  system (confirmed: `GRANT` is a parser error). The `gold_open`/`gold_restricted`
  schema split is structural/documentary here; real enforcement is the S3/IAM mapping
  already described in `working_contexts/` v2 §6.3, not something this track builds.
- A fourth or fifth mart beyond what the brief's 2–3 example queries need.

## Technical Notes

Full detail (schemas, contract YAML shape, all three marts' exact column tiers, the
`n_samples_with_unknown_patient` fix and why it exists, the `GRANT` limitation, storage
layout, CLI contract sketch) is in `../../../../scratch_pad.md`. Key resolved decisions
carried into the plan:

1. **4-tier column model** — `mandatory` (NULL excludes + quarantines),
   `good_to_have`/`okay_to_have` (NULL allowed, row stays, column present either way),
   `not_relevant` (column absent from the mart's schema entirely — doubles as
   minimization).
2. **Three marts:** `gold_open.gold_variant_gene_lookup_v1` (join),
   `gold_open.gold_cohort_gene_burden_v1` (aggregate),
   `gold_restricted.gold_sample_clinical_profile_v1` (restricted, full fidelity).
3. **`gene_symbol IS NULL` quarantine path has zero real-data coverage** (confirmed
   0/1089 rows) — its test must be synthetic, not pulled from the real cohort.
4. **`COUNT(DISTINCT patient_id)` alone silently drops `NULL`-patient samples** —
   `n_samples_with_unknown_patient` is a `mandatory` column specifically to prevent
   this from shipping as a silent undercount.
5. Naming convention unchanged from v2 §5.2:
   `<schema>.<zone>_<subject>_<purpose>_v<major>` (+ `_quarantine_v<major>` sibling).
6. Full rebuild every run (`CREATE OR REPLACE`), same as silver.
7. Stack: Python 3.14, `duckdb` (same engine, no new dependency) — per
   `conductor/tech-stack.md`.

---

_Generated by Conductor from `scratch_pad.md`. Review and edit as needed._
