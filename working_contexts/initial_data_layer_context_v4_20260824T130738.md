# Initial Data Layer — Working Context v4

| | |
|---|---|
| **Version** | v4 |
| **Created** | 2026-08-24 |
| **Status** | 🟢 **IMPLEMENTATION COMPLETE** — bronze, silver, gold all built, tested (105/105 passing), and documented. This version reconciles the v2/v3 *plan* against what actually got built — several real deviations, each with the reasoning that produced it. |
| **Supersedes** | `initial_data_layer_context_v3_20260823T203537.md` |

---

## 0. How to use this document

v2 (§1–§11) is the pre-implementation architecture plan. v3 added a bronze task
breakdown against that plan. **Implementation has since diverged from that plan in
several concrete, deliberate ways** — this version's job is to record what actually
got built, why it differs from what was planned, and where the living, continuously
verified detail now lives.

**This file does not duplicate the implementation detail.** That detail is
maintained where it can be checked against real code and real test output, not
copied prose that can drift out of sync:

- [`README.md`](../README.md) — bullets-first summary of every layer, with real
  verified numbers and runnable command examples.
- [`docs/data_architecture/{bronze,silver,gold}.md`](../docs/) — full per-layer
  detail: schemas, CLI options, internal-flow diagrams, example runs.
- [`docs/governance.md`](../docs/governance.md), [`docs/operations.md`](../docs/operations.md)
  — governance posture and operational posture (idempotency, reconciliation,
  the unmapped-vocabulary review flow).
- `conductor/tracks/_archive/{bronze,silver,gold}-layers_2026082*/` — the actual
  build history: spec → plan → phased implementation, with every design gap
  found during building recorded in place.

What belongs *here* instead: the decisions and the reasoning that a reader can't
get by reading the code — why bronze ended up joining when the plan said it
wouldn't, which v2 open questions are now actually resolved and how, what's still
genuinely deferred.

Markers, unchanged from v2: **RESOLVED** / **PROPOSED** / **OPEN** / ⚠️ (a
deviation from stated intent, with the reasoning).

---

## 1. Decisions resolved — updated against as-built reality

| ID | Decision | v2/v3 plan | **What was actually built** |
|---|---|---|---|
| **D1** | Storage engine & zone layout | Medallion: Parquet bronze / DuckDB silver / DuckDB gold | **Unchanged.** Built exactly as planned. |
| **D2** | Schema shape & grain | Bronze = five separate structural datasets (`variants`, `sample_manifest`, `vcf_headers`, `file_manifest`, `_quarantine`), unjoined; silver does the join | ⚠️ **Changed.** Bronze produces **one flat joined table** (`bronze.data` — sample × variant grain, manifest fields inlined) plus one narrow `bronze.quarantine` table. `vcf_headers` and `file_manifest` as persisted datasets were **not built** — see §2 below for why, and what was lost by not building them. |
| **D3** | Idempotency mechanism | Partition-level atomic replace, keyed on `batch_id` (re-running overwrites in place) | ⚠️ **Changed.** Bronze writes a **new timestamped file every run and never overwrites** — an audit-trail model, not a replace model. Silver and gold kept the planned full-rebuild (`CREATE OR REPLACE TABLE`) behavior unchanged. See §2. |
| **D4** | Conflict & defect policy | Three-tier defect granularity + never-drop/always-quarantine-with-reason; purpose-scoped quarantine in gold | **Unchanged in spirit, narrower in practice.** Bronze quarantines only genuinely unresolvable records (unparseable lines, conflicting manifest duplicates) — an *incomplete but combinable* record (e.g. a manifest row with no matching VCF) still lands in `bronze.data` with `NULL`s, never quarantined for incompleteness alone. Gold's per-mart quarantine (4-tier `mandatory`/`good_to_have`/`okay_to_have`/`not_relevant` contract) was built exactly as v2 §5 envisioned. |

---

## 2. Why bronze diverged from the plan (D2, D3)

**The join.** v2/v3 planned bronze as a pure structural landing zone — parse, don't
combine, leave the VCF↔manifest join to silver. During the bronze track, the
author redirected this explicitly: bronze should do the join and dedup itself,
producing one clean combined table rather than requiring every downstream
consumer to re-derive the join. The stated reasoning: querying bronze directly
(before silver/gold exist, or during silver's own development) is more useful
against an already-combined table, and the join itself is a *structural* fact
(which VCF rows correspond to which manifest row) rather than an interpretive
one — it doesn't require normalizing anything to compute.

**What this cost:** `bronze.vcf_headers` and `bronze.file_manifest` — the two
datasets v2 designed specifically to make schema drift (`CSQ`'s field order) and
file integrity (`S-0020`'s truncation) queryable independent of the row-level
parse — were not built as persisted bronze outputs. The header-drift parsing
(BR-2's `CSQ` `Format:` string parsing) still happens, but as an in-memory step
during row parsing, not as an auditable table. This is a real gap against v2's
intent, not a wash — flagged here rather than silently dropped, per this
project's own standard (§4 of this doc line of reasoning applies to itself).

**The narrower quarantine.** v3's BR-4 spec said bronze quarantines nothing at
the manifest level except malformed rows, landing both `S-0011` copies
uncollapsed for silver to resolve. The as-built bronze goes further: it resolves
*exact*-duplicate manifest rows itself (collapsing them, reported as `N exact
duplicates collapsed` in the CLI summary) and quarantines only the *irreconcilable*
case — rows that are duplicates on `sample_id` but disagree on a real field
(`S-0011`'s `tumor_purity`, `57%` vs `0.64`). The reasoning, stated directly by
the author during the bronze track: an exact duplicate carries zero information
to preserve by keeping both copies, so collapsing it in bronze isn't an
interpretive judgment call the way normalizing a value would be — it's the same
kind of structural fact as the join.

**The idempotency mechanism.** v2 §7 planned partition-replace: a re-run
overwrites the same `batch_id=<batch>/` path. What got built instead: every run
writes a **new** `data_<timestamp>.parquet` / `quarantine_<timestamp>.parquet`,
and nothing is ever overwritten. This makes bronze a genuine append-only audit
trail — every historical run is still on disk, inspectable — at the cost of
`warehouse/bronze/data/<batch_id>/` accumulating one file per run over time.
Downstream, this is safe by construction, not by convention: silver's
auto-discovery reads only the lexicographically-latest file per batch directory
(confirmed in `silver_builder/discover.py`), so accumulation never causes a
double-count — see [`docs/data_architecture/silver.md`](../docs/data_architecture/silver.md#command-and-options)
for the direct verification of that claim, which came up as an explicit user
question this session (*"wouldn't running silver/gold with no options cause
conflicts and duplicate updates?"* — answered: no, and here's the code path that
makes that true, not just an assertion).

**Skip-if-unchanged (`--force`, BR-8) was not built.** Every `data-loader` run
processes fully, regardless of whether the source files changed since the last
run — the intentional consequence of never-overwrite is that a duplicate-content
re-run is cheap to *have* (it's just another audit-trail entry) but not free to
*produce* (full reparse every time). Not flagged as a problem at this data
volume (fractions of a second); would be the first idempotency-adjacent thing to
revisit at the "what changes at 1000×" scale discussed in v2 §9.

---

## 3. Bronze / silver / gold — as-built, pointer-only

Full schemas, CLI contracts (every flag explained, with real example
invocations and real output), exit codes, and per-layer internal-flow diagrams
now live in `docs/data_architecture/`, verified against actual pipeline runs,
not written from the plan:

- **Bronze** — [`docs/data_architecture/bronze.md`](../docs/data_architecture/bronze.md).
  Verified: `batch_2026_01` → 795 rows, 2 quarantined; `batch_2026_02` → 295
  rows, 1 quarantined.
- **Silver** — [`docs/data_architecture/silver.md`](../docs/data_architecture/silver.md).
  Verified: 1090 bronze rows in → 20 samples, 1089 variant calls, 0
  silver-level quarantine.
- **Gold** — [`docs/data_architecture/gold.md`](../docs/data_architecture/gold.md).
  Verified: `gold_variant_gene_lookup_v1` 1032 rows/57 quarantined,
  `gold_cohort_gene_burden_v1` 36 rows/0 quarantined,
  `gold_sample_clinical_profile_v1` 17 rows/3 quarantined.

Real defects found and fixed **during** implementation, not anticipated by the
plan — full account in [`README.md`'s AI assistance note](../README.md#ai-assistance-note):

- Bronze: the original spec would have silently dropped `S-0011`'s valid
  variant calls over an unrelated manifest-field conflict — caught in testing,
  fixed to land with manifest columns `NULL`.
- Silver: `batch_2026_02`'s `VAF` field was on a 0–100 scale against
  `batch_2026_01`'s 0–1 — a real cross-batch data-quality defect, not
  anticipated in v1/v2's profiling, found by cross-checking `AD`/`DP`.
- Gold: `COUNT(DISTINCT patient_id)` would have silently dropped `S-0011` from
  every gene's patient count (SQL drops `NULL` in `COUNT(DISTINCT ...)`) — found
  before shipping, fixed by adding `n_samples_with_unknown_patient`.

---

## 4. v2 open questions (§8) — resolved or carried forward

| ID | Question | Status now |
|---|---|---|
| **O1** | Multi-sample VCF grain | **RESOLVED.** Built generally, not against this data's single-sample-column shape by luck: `vcf_headers.py` parses `sample_columns` as a list from the `#CHROM` header (`columns[9:]`), and `vcf_rows.py` iterates `zip(contract.sample_columns, genotype_raws)` per line — a multi-sample VCF would already produce one row per (sample, variant) correctly. |
| **O2** | Variant normalisation (multi-allelic splitting, left-alignment) | **Still OPEN.** No `bcftools norm`-equivalent step exists anywhere in the pipeline. This data has none of those cases (confirmed, not assumed, in v1 profiling), so it was never forced. Still the first thing named to break at real-world scale — unchanged from v2 §8/§9. |
| **O3** | `MAX_POP_AF` vs `GNOMAD_AF_POPMAX` | **Resolved as v2 intended: documented, not chosen.** Both are normalized to `[0,1]` independently in silver (`normalize_af()` applies to both); neither is preferred over the other or merged. Which one a mart uses remains a researcher decision, not a modelling one. |
| **O4** | Non-PASS calls in gold | **RESOLVED.** Confirmed directly in the contract YAMLs: only `gold_variant_gene_lookup_v1` filters (`filter IS NULL OR filter = 'PASS'`); `gold_cohort_gene_burden_v1` and `gold_sample_clinical_profile_v1` both have `filters: []` — non-PASS calls remain fully available in two of the three marts. The 4-tier contract model (built after v2 was written) turned out to be exactly the mechanism O4 was asking for: per-mart filtering as a declared, inspectable contract rather than a single hardcoded pipeline-wide choice. |
| **O5** | Testing depth | **RESOLVED.** 105 tests across bronze/silver/gold — parsers, reconciliation invariants asserted as real failing tests (not eyeballed), and (per §2 above) idempotency-adjacent behavior covered by the silver auto-discovery + full-rebuild tests, though the original "run twice, diff byte-for-byte" idempotency test (TB-5) doesn't apply in the same form since bronze no longer overwrites — replaced in spirit by tests asserting re-running never double-counts downstream. |

**One new deferred item, not in v2 at all:** the agentic vocabulary-authoring
loop (v2 §4.4) has its runtime half built — deterministic crosswalk lookup, no
LLM in the execution path, exactly as v2 specified. The *authoring* half — what
happens the next time silver quarantines a genuinely new unmapped value — was
never built as a distinct tool; it happened informally while hand-writing the
crosswalk YAMLs during the silver track. A full review → propose → human-approve
→ commit flow is designed (with its own diagram) in
[`docs/operations.md`](../docs/operations.md#next-phase-unmapped-vocabulary-review),
recorded as an explicit next-phase recommendation, not silently left
undocumented.

---

## 5. Non-goals (v2 §9) — status check, not restated

All six non-goals in v2 §9 held throughout implementation, confirmed rather than
assumed:

- No imputation — confirmed: every quarantine/exclusion path found during
  implementation (bronze's `S-0011`, gold's `n_samples_with_unknown_patient`)
  was fixed by *surfacing* the gap as a new column or quarantine reason, never
  by filling it in.
- No LLM in the execution path — confirmed: silver's normalization/crosswalk
  code is pure deterministic lookup; no model call anywhere in
  `data_loader`/`silver_builder`/`gold_builder`.
- The malformed file (`S-0020`) was handled, not special-cased away — it
  produces exactly one quarantined row via the same structural parse-failure
  path every other malformed line goes through.
- No variant normalisation — confirmed still absent (O2, above).
- No cloud infrastructure — confirmed: `uv sync` + local DuckDB/Parquet is the
  entire runtime. (The DuckDB **CLI** binary, installed via Homebrew this
  session purely as an interactive inspection tool for `warehouse/*.duckdb` and
  the Parquet files directly, doesn't change this — it's a developer
  convenience outside the pipeline, not a new runtime dependency; the pipeline
  itself uses only the Python `duckdb` package, already declared in
  `pyproject.toml`.)
- No incremental silver/gold — confirmed: both remain full `CREATE OR REPLACE`
  rebuilds every run, exactly as v2 §7/§9 planned.

---

## 6. Governance and access — unchanged, pointer only

v2 §6's governance design was built and documented without deviation. Full
detail — the per-tier de-identification argument, the honest k-anonymity
limitation, the `GRANT`-is-unsupported finding (embedded DuckDB has no
role/grant system, checked directly), the production S3-to-S3 IAM mapping, and
what an AI assistant needs to answer reliably — now lives in
[`docs/governance.md`](../docs/governance.md), moved there verbatim from an
earlier README revision, verified by diff at the time of the move (see the
`docs-restructure_20260824` conductor track).

---

## 7. AI assistance log addendum

| Area | Use | Trust posture |
|---|---|---|
| Bronze design redirect (join + dedup in bronze, not silver) | Author-directed mid-build correction to v2/v3's plan | Author's decision; AI implemented and is recording the resulting D2/D3 deviation here, since it wasn't captured anywhere until this version |
| Gold's case-by-case mart model (4-tier contracts) | Author-directed: explicit rejection of a single generic gold schema, in favor of per-mart column-relevancy contracts | Author's decision; turned out to directly resolve v2's open question O4 as a side effect, noted in §4 |
| Bronze/silver/gold implementation gaps (`S-0011`, `VAF` ×100, `n_samples_with_unknown_patient`) | AI found each while verifying the plan against real data during implementation, before or during test-writing | **Verified** — each reproducible by a command against real files; full account in `README.md`'s AI assistance note, not duplicated here |
| This version's D2/D3 divergence writeup | AI synthesized from conversation history + a fresh read of `data_loader/join.py`, `discover.py`, `writer.py`, and the gold contract YAMLs, not from memory of what was planned | Re-verified against actual code in this session (§1's table, §2's join/quarantine/idempotency claims, §4's O1/O4 resolutions) rather than asserted from v2/v3's plan text |

---

## 8. Changelog

**v4 (2026-08-24)** — Reconciles the v2/v3 pre-implementation plan against the
now-complete, tested, documented implementation.

- Recorded three real architecture deviations from the v2/v3 plan, each with
  the author's stated reasoning: bronze now joins + dedups exact duplicates
  itself (D2 changed); `bronze.vcf_headers`/`bronze.file_manifest` were not
  built as persisted datasets (a real, flagged gap against v2's intent);
  bronze's idempotency mechanism is append-only-audit-trail, not
  partition-replace (D3 changed).
- Resolved v2 §8 open questions **O1** (multi-sample VCF — built generally,
  verified in code), **O4** (non-PASS calls in gold — per-mart contract
  filtering answers it directly), and **O5** (testing depth — 105 tests).
  **O2** (variant normalisation) remains genuinely open. **O3** (`MAX_POP_AF`
  vs `GNOMAD_AF_POPMAX`) resolved exactly as v2 intended — documented, not
  merged.
- Added one new deferred item not present in v2: the agentic
  vocabulary-authoring loop's authoring half (only the runtime half was ever
  planned as built-this-pass) — now a designed, undocumented-no-longer,
  explicitly next-phase recommendation.
- Stopped duplicating implementation detail into `working_contexts/` — this
  version points to `README.md` and `docs/` (built, verified, and kept in sync
  with real pipeline output by the `docs-restructure_20260824` track) rather
  than re-describing schemas/CLIs that already have a living, checked home.
- Confirmed all six v2 §9 non-goals held through implementation; noted the
  DuckDB CLI's addition to the local dev environment as a non-change to the
  no-cloud-infrastructure non-goal (inspection tool, not a runtime dependency).
