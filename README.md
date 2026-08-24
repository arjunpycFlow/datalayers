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
> quarantined (`S-0020`'s truncated line).

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
> (`conductor/tracks/_archive/silver-layer_20260823/`, all 6 phases). Verified
> against real bronze output for both batches: 1090 rows in → 20 samples, 1089
> variant calls, 0 silver-level quarantines (the known real-data defects were
> already handled at bronze). Example queries confirmed against real data: `TP53`
> has 57 variants but only 17 distinct patients — the exact denominator trap
> `n_distinct_patients` exists to prevent.

## Running the gold-layer builder

`gold_builder` reads `warehouse/silver.duckdb` and writes **purpose-scoped marts**
to `warehouse/gold.duckdb` — one mart per research question, each with its own
column-relevancy contract rather than one generic schema:

```bash
uv run gold-builder
```

Builds every contract found in `config/gold_contracts/`. To build just one:

```bash
uv run gold-builder --mart gold_variant_gene_lookup_v1
```

**Exit codes:** `0` success · `1` `--silver-db` not found · `2` reconciliation or
schema-minimization invariant failed (a bug, not a data defect).

**The three marts:**

| Mart | Schema | Grain | Answers |
|---|---|---|---|
| `gold_variant_gene_lookup_v1` | `gold_open` | (sample, variant) | *"Which samples carry a variant in gene X, and what tissue/diagnosis are they from?"* |
| `gold_cohort_gene_burden_v1` | `gold_open` | gene | *"How many variants per gene, and how many distinct patients?"* |
| `gold_sample_clinical_profile_v1` | `gold_restricted` | sample | Full-fidelity clinical context for correlation work needing exact dates/purity |

**Each mart's columns are tiered** `mandatory` / `good_to_have` / `okay_to_have` /
`not_relevant` (`config/gold_contracts/*.yaml`) — only a `mandatory`-tier `NULL`
excludes a row (quarantined, with a reason); lower tiers never exclude, they just
land `NULL`; `not_relevant` columns are dropped from that mart's schema entirely,
not merely left nullable. The same silver row can be excluded from one mart and
fully counted in another — both correct, for different reasons. Concrete, verified
example: `S-0011` (its manifest fields are `NULL` — a bronze-layer decision, not a
defect) is excluded from `gold_variant_gene_lookup_v1` (`tissue` is `mandatory`
there) but its 3 `TP53` variants are still counted in
`gold_cohort_gene_burden_v1`'s `n_variants` — while correctly *not* counted in
`n_distinct_patients` (its `patient_id` is `NULL`, and SQL's
`COUNT(DISTINCT ...)` silently drops `NULL` — a real gap found while building this,
fixed by adding `n_samples_with_unknown_patient` as its own column so the gap is
visible instead of hidden).

> **Status:** gold layer complete
> (`conductor/tracks/_archive/gold-layers_20260823/`, all 6 phases). Verified
> against real silver output: `gold_variant_gene_lookup_v1` → 1032 rows, 57
> quarantined (all `S-0011`); `gold_cohort_gene_burden_v1` → 36 rows (one per
> gene), 0 quarantined; `gold_sample_clinical_profile_v1` → 17 rows, 3 quarantined
> (`S-0003` missing `tumor_purity`, `S-0011` fully `NULL`, `S-0012` missing
> `collection_date` — all three previously-known real gaps in the source manifest,
> not new surprises).

## Governance note

*(Required by the brief: "how would you handle de-identification and access
control before researchers touch this, and what would you document so an AI
assistant could answer questions on this data reliably?")*

**De-identification is per-tier, not global** — each `gold_open` mart drops
(rather than merely masks) any quasi-identifying column it doesn't need for its
specific purpose (`gold_variant_gene_lookup_v1` never carries `patient_id` or
`collection_date` at all, not even generalised — the question it answers doesn't
need them). `gold_restricted.gold_sample_clinical_profile_v1` carries exact dates
and purity, gated to narrow, named, audited access.

**The honest limitation, stated plainly, not implied away:** at n=20, k-anonymity
is not achievable by generalisation — binning `collection_date` to month only moves
the cohort from 20/20-unique to 9/20-unique (`working_contexts/` v1 §4), and more
fundamentally, **the variant data is itself an identifier** (30–80 common SNPs
uniquely identify a person and their biological relatives) — stripping names from a
VCF is not de-identification in any meaningful sense. **The control is access, not
anonymisation.** Column minimization via the 4-tier contract model reduces each
mart's attack surface; it is not a claim that the data is anonymous.

**The `gold_open`/`gold_restricted` schema split is structural, not enforced
access control** — checked directly: embedded DuckDB has no `GRANT`/role system
(`GRANT SELECT ON SCHEMA ... TO ...` is a parser error). Real enforcement is the
S3-to-S3 production mapping already designed in `working_contexts/` v2 §6.3 — a
separate IAM role per zone, each able to read exactly one zone and write exactly
one, with per-prefix policy and CloudTrail auditing on the restricted tier. This
repo's schema split is the structural analog of that boundary, not the boundary
itself.

**What an AI assistant needs, to answer reliably rather than guess:** each mart's
declared `purpose` and `grain` (in its contract YAML, and queryable from
`DESCRIBE`); denominator-safe column names (`n_variants` vs. `n_distinct_patients`
vs. `n_samples_with_unknown_patient` — never a bare `count`); the quarantine
semantics note above (`_quarantine_v1` siblings are *not* bad data — they're data
that didn't meet *that mart's* contract, and may be valid elsewhere); and the fact
that `not_relevant` means a column is absent, not that it happened to be `NULL`.

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
`conductor/tracks/_archive/silver-layer_20260823/plan.md` (Phase 4).

**Gold layer — a genuine silent-undercount, found and fixed before implementation:**
while verifying the planning doc against real data (not just trusting the plan),
found that the originally-designed `n_distinct_patients =
COUNT(DISTINCT patient_id)` would have silently excluded `S-0011` from every gene's
patient count — SQL's `COUNT(DISTINCT ...)` drops `NULL` silently, and `S-0011`'s
`patient_id` is `NULL`. Confirmed directly: `S-0011` contributes 3 real variants to
`TP53` (57 vs. 54 without it), but none of them would have shown up in a bare
`n_distinct_patients`. Fixed by adding `n_samples_with_unknown_patient` as its own
column before any code was written against the flawed design — the same
"don't silently drop" principle applied everywhere else in this project, just
caught here via SQL semantics rather than application logic. Also corrected two
smaller claims during the same verification pass: an initial check for the same
kind of outlier in `MAX_POP_AF` was itself wrong (real data has none there), and the
gold naming convention's "`schema` is the unit of `GRANT`" language needed a
caveat — embedded DuckDB has no `GRANT` at all. All recorded in
`conductor/tracks/_archive/gold-layers_20260823/plan.md` (Phases 3–4).
