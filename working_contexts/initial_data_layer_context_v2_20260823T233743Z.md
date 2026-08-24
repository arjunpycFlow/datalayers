# Initial Data Layer — Working Context v2

| | |
|---|---|
| **Version** | v2 |
| **Created** | 2026-08-23T23:37:43Z |
| **Status** | 🟢 **ARCHITECTURE RESOLVED** — medallion adopted; implementation not started |
| **Supersedes** | `initial_data_layer_context_v1_20260822T232859Z.md` |

---

## 0. How to use this document

`AGENTS.md` holds stable operating rules. **This file holds the architecture and the
decisions behind it.** It is append-only — to revise, write `v3`.

Markers used below:

- **RESOLVED** — decided; build to this.
- **PROPOSED** — recommended, awaiting confirmation.
- **OPEN** — genuinely undecided.
- ⚠️ — a deviation from the author's stated intent, with the reasoning. Overrule freely,
  but read the argument first.

**Everything in v1 §3 (landing-zone defect profile) and §4 (re-identification analysis)
remains valid and is not restated here.** Read v1 for the underlying facts; this document
assumes them.

---

## 1. Decisions resolved

| ID | Decision | Resolution |
|---|---|---|
| **D1** | Storage engine & zone layout | **RESOLVED** — Medallion. Bronze = Parquet on disk, partitioned by batch. Silver = DuckDB. Gold = DuckDB schemas, materialised. |
| **D2** | Schema shape, grain, drift handling | **RESOLVED** — Typed core + semi-structured `info` map in bronze; conformed relational model in silver; narrow purpose-built marts in gold. Drift absorbed additively via `union_by_name`. |
| **D3** | Idempotency | **RESOLVED** — Partition-level replace, keyed on `batch_id`. See §7. |
| **D4** | Conflict & defect policy | **RESOLVED** — Three-tier defect granularity + never-drop / always-quarantine-with-reason. Extended in gold to **purpose-scoped quarantine**. See §5.4. |

---

## 2. Architecture

```
candidate_bundle/data/                    IMMUTABLE LANDING ZONE (read-only)
  batch_2026_01/  *.vcf + sample_manifest.csv
  batch_2026_02/  *.vcf + sample_manifest.csv
        │
        │  parse · trim · structure · NEVER interpret
        ▼
BRONZE   warehouse/bronze/**.parquet       Parquet on disk, Hive-partitioned by batch_id
         fidelity layer — nothing lost, nothing judged
        │
        │  conform · type · normalise vocabulary · deduplicate
        ▼
SILVER   warehouse/silver.duckdb           one conformed, trustworthy relational model
         trust layer — one row per real-world thing
        │
        │  select columns per purpose · enforce completeness contract
        ▼
GOLD     warehouse/gold.duckdb             many narrow, purpose-built marts
         gold_open.*      (de-identified, broad access)
         gold_restricted.* (full fidelity, narrow access)
         + a quarantine sibling for every mart
```

**The layer contract in one line each:**

- **Bronze answers:** *"what exactly arrived?"* — optimised for fidelity and audit.
- **Silver answers:** *"what is true?"* — optimised for correctness and reuse.
- **Gold answers:** *"what can I rely on for **this** question?"* — optimised for a single
  named purpose, and for an NL assistant that must not guess.

---

## 3. Bronze layer — RESOLVED

### 3.1 Principles

1. **Fidelity over cleanliness.** If a value was in the file, it is in bronze.
2. **Structure, don't interpret.** Split the record into fields; do not decide what a
   field *means*. `"63%"` stays `"63%"`. `"LUNG "` becomes `"LUNG"` (trim only).
3. **Everything is a string except what VCF itself declares typed.** Type coercion is
   silver's job and is a decision that must be reversible.
4. **Nothing is dropped.** Rows that cannot be parsed are routed to a bronze quarantine
   dataset *with their raw text*, not discarded.
5. **Provenance on every row** — source file, batch, pipeline version, ingest run id,
   source line number.

### 3.2 The one unavoidable conversion ⚠️

The stated intent was "no conversion of anything." One conversion is nonetheless
**mandatory**, and it is the exception that makes the rule work:

> **VCF's missing-value sentinel `.` must become a real NULL.**

VCF uses the literal character `.` to mean "no value" in `ID`, `QUAL`, and elsewhere
(361 of 1090 rows have `QUAL = "."` — see v1 §3.3 V2). Storing the literal string `"."`
means every downstream consumer must know that `.` is special, and the NL assistant
certainly will not. `WHERE qual IS NULL` is correct and discoverable; `WHERE qual = '.'`
is tribal knowledge.

To preserve fidelity despite this, bronze also carries **`raw_line`** — the complete,
verbatim, untouched source line. Parquet compresses this extremely well (it is highly
repetitive), and it means bronze is *provably* lossless: any parsing decision can be
re-derived or audited without returning to the landing zone.

**Permitted bronze transformations, exhaustively:**

| # | Transformation | Rationale |
|---|---|---|
| 1 | Split on tabs / commas into fields | Structural, reversible |
| 2 | Strip leading/trailing whitespace | Whitespace is never semantic here |
| 3 | `"."` → NULL for VCF-declared missing markers | See above |
| 4 | Empty string `""` → NULL | Same reasoning |
| 5 | Parse `INFO` into a `MAP(VARCHAR, VARCHAR)` | Structural; **`HOTSPOT`-style Flags map to key → `'true'`** (v1 §3.3 V1) |
| 6 | Parse `CSQ` into a `MAP` **using the sub-field order declared in the file's own `##INFO=<ID=CSQ...Format:...>` header** | This is the drift test (v1 §3.3 V6). Never hardcode positions. |

**Explicitly NOT done in bronze:** date parsing, `%`→fraction conversion, case
normalisation, vocabulary mapping, deduplication, type casting beyond the above,
cross-record validation.

### 3.3 NULL handling in Parquet — question answered

> *"Is it required to fill in NULL if a value is missing for a column equivalent in Parquet?"*

**No — and you must not use a sentinel.**

Parquet has **native nullability**. Each column is declared `optional`, and nullness is
recorded out-of-band in *definition levels*, which are run-length encoded. A column that
is entirely NULL for a batch costs approximately nothing — there is no per-row placeholder
value stored at all. You write `None` / `null` and the format handles it.

The failure mode to avoid is writing a **sentinel** — `""`, `"."`, `"NA"`, `-1`, `0`.
Sentinels are indistinguishable from real values, they poison aggregates (a `0` purity is
not a missing purity), and they defeat `IS NULL`. This is the single most common way a
bronze layer silently corrupts everything above it.

**Corollary for schema drift:** batch-1 files have no `CCF` field. You do **not** add a
NULL-filled `CCF` column to batch-1 Parquet files. You simply omit it, and read across
batches with:

```sql
SELECT * FROM read_parquet('warehouse/bronze/variants/**/*.parquet', union_by_name = true);
```

DuckDB unions on column name and yields `CCF = NULL` for batch-1 rows automatically.
That is the entire additive-schema-evolution mechanism — no migration, no backfill, no
touching batch-1 data.

### 3.4 Parquet file sizing — question answered

> *"1 Parquet per batch, or a set if there are file size constraints — any performance limitation on Parquet file size?"*

**There is no hard size limit in the format.** The constraints are practical:

| Parameter | Guidance | Why |
|---|---|---|
| Target file size | **128 MB – 1 GB** | Below ~64 MB you hit the *small-file problem* (per-file metadata and open costs dominate). Above ~1–2 GB you lose read parallelism and strain writer memory. |
| Row group size | **~128 MB**, or ~500k–1M rows | The row group is the unit of parallelism *and* of predicate pushdown / statistics pruning. One giant row group means no pruning. |
| Page size | 1 MB default | Rarely worth tuning |
| Compression | **ZSTD** (level 3) | Better ratio than Snappy at comparable speed; excellent on the repetitive `raw_line` column |

**For this dataset specifically:** the entire cohort is ~250 KB. One Parquet file per
batch is already far below any threshold where sizing matters. **This should be stated
plainly in the submission README** — partitioning here is demonstrating the pattern, not
solving a present problem, and claiming otherwise would be dishonest about scale.

**The rollover rule to implement anyway** (so the pattern is real, not decorative):
write `part-00000.parquet`, `part-00001.parquet`, … within a partition, rolling to a new
part at a configurable `max_rows_per_file` / `max_bytes_per_file`. Default it to
512 MB. At current volume it will never trigger; at 1000× it does the right thing with
no code change.

### 3.5 Layout and partitioning

```
warehouse/bronze/
├── variants/
│   ├── batch_id=batch_2026_01/part-00000.parquet
│   └── batch_id=batch_2026_02/part-00000.parquet
├── sample_manifest/
│   ├── batch_id=batch_2026_01/part-00000.parquet
│   └── batch_id=batch_2026_02/part-00000.parquet
├── vcf_headers/
│   └── batch_id=.../part-00000.parquet
├── file_manifest/
│   └── batch_id=.../part-00000.parquet
└── _quarantine/
    └── batch_id=.../part-00000.parquet
```

Hive-style `key=value` directories, because DuckDB, Spark, Athena and Glue all understand
them natively, and because **the directory layout is literally the S3 prefix layout** —
which makes the production access-control story concrete rather than hypothetical (§6.3).

⚠️ **Partition by `batch_id` only.** Do not additionally partition by chromosome, gene,
or sample. Over-partitioning is the more common and more damaging mistake — it produces
thousands of tiny files and degrades every query. Revisit only when a single batch
partition genuinely exceeds ~1 GB.

### 3.6 Bronze datasets and grain

| Dataset | Grain | Notes |
|---|---|---|
| `bronze.variants` | **one row per variant call per sample** — i.e. one row per data line per VCF file | Uniquely keyed by `(source_file, source_line_no)`. Since these VCFs carry exactly one sample column each, this equals variant × sample. ⚠️ See §8 O1 — this assumption breaks for multi-sample VCFs. |
| `bronze.sample_manifest` | **one row per manifest CSV row** | **Includes the duplicate `S-0011` rows — both of them.** Bronze does not deduplicate; that is a judgment, and judgments live in silver. |
| `bronze.vcf_headers` | one row per `(source_file, header_type, header_id)` | Captures every `##INFO` / `##FORMAT` / `##FILTER` / `##contig` declaration with its `Type`, `Number`, `Description`. **This makes schema drift itself queryable** — "which INFO fields appeared in which pipeline version?" becomes SQL rather than folklore. Strongly recommended; it is cheap and it is the artifact that proves drift was handled deliberately. |
| `bronze.file_manifest` | one row per source file | Byte size, SHA-256, row count, parse status, `is_truncated`, `##source` pipeline version, `##reference`, ingest run id. The integrity ledger. |
| `bronze._quarantine` | one row per unparseable source line | Carries `raw_line`, `source_file`, `source_line_no`, `reason_code`, `reason_detail`. |

**Common provenance columns on every bronze row:** `batch_id`, `source_file`,
`source_line_no`, `pipeline_version`, `ingest_run_id`, `ingested_at_utc`.

### 3.7 The truncated file (`S-0020`) — refined handling ⚠️

v1 concluded "quarantine the whole file." **This is now refined**, because bronze's job is
fidelity and silver's job is trust — conflating them loses information:

| Layer | Action on `S-0020` |
|---|---|
| **Bronze** | Land all **100 valid rows** normally. Route the truncated line 101 to `bronze._quarantine` with `reason_code = 'TRUNCATED_RECORD'`. Record `parse_status = 'TRUNCATED'`, `is_truncated = true` in `bronze.file_manifest`. **Nothing is lost.** |
| **Silver** | **Exclude sample `S-0020` entirely**, on the strength of the bronze file-level verdict. Reason code `SOURCE_FILE_TRUNCATED`. |
| **Gold** | `S-0020` is absent, and therefore counted as **missing**, never as **zero**. |

This keeps the v1 conclusion's *outcome* — a truncated sample must never contribute to a
cohort aggregate, because truncation is unbounded and would silently understate that
patient's mutational burden — while preserving the raw evidence for investigation. The
partial data remains inspectable in bronze by anyone diagnosing the transfer failure; it
simply cannot leak into analytics.

**Detection, for the README's "how would you detect this in production" answer:**

1. **Producer-side manifest** — the pipeline emits expected byte size + checksum + record
   count per file; ingestion verifies before parsing. This is the real answer.
2. **S3-native integrity** — `Content-MD5` / checksum on upload; only complete multipart
   uploads become visible objects; process on `s3:ObjectCreated:*` rather than polling.
3. **Structural validation** — last byte is a newline; every data line has exactly
   `9 + n_samples` tab-separated fields.
4. **Statistical tripwire** — variant count per sample outside the cohort's historical
   distribution flags for review.
5. **In production, bgzip + tabix index** — the BGZF EOF marker makes truncation
   detectable at the format level, which is precisely why production VCFs are shipped
   that way (the brief notes this).

---

## 4. Silver layer — RESOLVED

**Store: DuckDB** (`warehouse/silver.duckdb`).

### 4.1 Principles

1. **One row per real-world thing.** Grain is declared and enforced per table.
2. **Every value conformed to a declared standard.** Units, formats, vocabularies.
3. **Deterministic and reproducible.** Same input → byte-identical output, always.
4. **Every exclusion is recorded, never silent.**

### 4.2 Normalisation rules

| Field | Rule |
|---|---|
| `collection_date` | Parse all 5 observed formats. **`DD/MM/YYYY` for slash-ambiguous values**, justified by batch-window consistency (v1 §3.2 M1) — record this as a documented assumption. Unparseable → NULL + flag, never guess. |
| `tumor_purity` | Normalise to **fraction in [0, 1]**. `"63%"` → `0.63`. Reject and quarantine anything outside [0, 1] after conversion — that is the guard against the `63.0` bug. |
| `tissue`, `diagnosis`, `platform`, `library_prep`, `qc_status` | Map to a **controlled vocabulary** via a checked-in crosswalk. See §4.3. |
| `sex_reported`, `sex_inferred` | Normalise to `M` / `F` / NULL **independently**. Add derived `sex_concordant BOOLEAN`. ⚠️ **Never reconcile them** — `S-0007`'s discordance is a QC finding (possible sample swap), not a formatting defect. |
| `qc_status` | Empty → NULL, **not** `PASS`. A sample with no verdict has not passed. |
| `notes` | Retain, **plus** derived boolean flags: `is_ffpe`, `is_repeat_library`. FFPE causes characteristic C>T artefacts, so it is analytically meaningful, not prose. |

### 4.3 Timezone handling ⚠️ — correction to stated intent

The stated intent was to store dates "in UTC with timezone information captured."
**For `collection_date` this is wrong, and would introduce a real bug.**

`collection_date` is a **calendar date**, not an instant. The source carries no time and
no zone — `"Jan 5 2026"` is a date on which a specimen was collected. Attaching a
timezone requires *inventing* a time (typically midnight) and a zone, and then any later
conversion can **shift the calendar date by a day**. That is silent data corruption of a
clinical field, in service of precision that does not exist.

**The correct distinction:**

| Kind of field | Type | Example |
|---|---|---|
| **Event dates** (no time in source) | `DATE` — no zone, ever | `collection_date`, `vcf_file_date` (from `##fileDate`) |
| **System timestamps** (real instants we generate) | `TIMESTAMPTZ`, **UTC** | `ingested_at_utc`, `run_started_at_utc`, `promoted_at_utc` |

So the UTC instinct is right — it just applies to *our* timestamps, not to *their* dates.
Storing UTC system timestamps and zone-free event dates is the standard, defensible
answer, and it is the kind of distinction an interviewer is likely to probe.

### 4.4 Vocabulary normalisation: agent-assisted, deterministic at runtime ⚠️

The stated intent was an **agentic solution** that reads context to resolve `"LUNGS"`,
`"LUNG "`, `"lung"` to a standard value. The instinct — use the model's judgment for
messy human text — is right. **But an LLM must not sit in the pipeline's execution
path**, for four reasons:

1. **Non-determinism breaks the assignment's own requirement.** The brief demands
   re-runnability ("running it twice should not corrupt or duplicate data") and
   single-command reproduction from a clean checkout. An LLM can map `"LUNG "` to `Lung`
   on Monday and `Lung, NOS` on Tuesday. Two runs, two datasets.
2. **It is unauditable.** For clinical data, "why is this sample labelled Lung?" must
   have an answer better than "the model said so." A regulator, or a researcher chasing
   an anomaly, needs a reviewable rule.
3. **It does not scale.** One inference per row per column at 1000× is absurd cost and
   latency for what is fundamentally a lookup.
4. **It is unnecessary here.** The vocabulary has ~6 values.

**Resolution — the agent moves from the execution path to the authoring loop:**

```
   unmapped value appears
            │
            ▼
   ┌────────────────────┐   proposes mapping + rationale + confidence
   │  AGENT (authoring) │──────────────────────────────────────────┐
   └────────────────────┘                                          │
            │                                                      ▼
            │                                          ┌──────────────────────┐
            │                                          │  HUMAN REVIEW        │
            │                                          │  approve / correct   │
            │                                          └──────────────────────┘
            │                                                      │
            ▼                                                      ▼
   pipeline QUARANTINES the row              committed to  config/crosswalks/tissue.yaml
   (reason: UNMAPPED_VOCABULARY_TERM)                    (version-controlled, reviewable)
            │                                                      │
            └──────────────► next run applies it DETERMINISTICALLY ◄┘
```

The crosswalk is a version-controlled YAML file. The pipeline is a pure lookup —
deterministic, instant, auditable, diff-reviewable. **An unmapped value is quarantined
and alerts; it is never guessed at at runtime.** The agent accelerates *writing* the
crosswalk; it never *is* the crosswalk.

This is a stronger answer than "we use an LLM to clean data," because it demonstrates
knowing **where non-determinism is acceptable** — and it is directly relevant to a
company building an NL assistant on this foundation.

Example crosswalk entry:

```yaml
# config/crosswalks/tissue.yaml
version: 1
canonical_terms: [Lung, Breast, Colon, Stomach, Pancreas]
mappings:
  "lung":   Lung
  "LUNG":   Lung
  "Lung":   Lung
  "breast": Breast
  "COLON":  Colon
on_unmapped: quarantine   # never: guess
```

### 4.5 Deduplication and conflict resolution

| Case | Silver behaviour |
|---|---|
| **`S-0011` duplicate, conflicting `tumor_purity` (`57%` vs `0.64`)** | **Load neither.** Quarantine both rows, `reason_code = 'CONFLICTING_DUPLICATE'`, `reason_detail` naming the divergent column and both values. There is no ingestion timestamp or row version in the source that would justify picking a winner, and inventing a tiebreak (last-row-wins) is a silent coin flip on a clinical attribute. ⚠️ Note the variant data for `S-0011` is unaffected and still loads — only the *manifest* row is ambiguous. This is exactly the value-vs-record granularity distinction. |
| **`S-0008` in manifest, no VCF** | Load the manifest row into `silver.samples` with `has_variant_data = false`, **and** emit a quarantine record `reason_code = 'ORPHAN_MANIFEST_ROW'`. It is a real sample whose file failed to land — that is an operational incident to surface, not a row to erase. |
| **VCF present with no manifest row** | Same treatment inverted: `reason_code = 'ORPHAN_VARIANT_FILE'`. Does not occur in this data; implement anyway. |
| **`S-0020` truncated** | Excluded, `reason_code = 'SOURCE_FILE_TRUNCATED'` (§3.7). |
| **Exact duplicate rows** (all columns equal) | Safe to collapse — log the count, no quarantine. Does not occur here. |

### 4.6 Silver tables and grain

| Table | Grain | Key |
|---|---|---|
| `silver.patients` | **one row per patient** | `patient_id`. Note `P-0003` has two samples (v1 §3.2 M6) — this table is why cohort counts can state their denominator. |
| `silver.samples` | **one row per sample** | `sample_id` → `patient_id` |
| `silver.variant_calls` | **one row per (sample, variant)** | `(sample_id, chrom, pos, ref, alt)` |
| `silver.variant_annotations` | **one row per (sample, variant, transcript)** | ⚠️ Currently 1:1 with `variant_calls` because this synthetic `CSQ` carries a single annotation. **Real VEP output is one row per transcript.** Modelling it separately now costs nothing and means the grain does not change when real data arrives. Documented explicitly. |
| `silver.batches` | one row per batch | `batch_id`, pipeline version, file counts, ingest run |
| `silver.quarantine` | one row per excluded record | `source_layer`, `source_file`, `source_line_no`, `entity_type`, `entity_id`, `reason_code`, `reason_detail`, `quarantined_at_utc` |

**Reference/dimension tables** (derived, because `diagnosis → disease_group` is a strict
functional dependency — v1 §4): `silver.ref_diagnosis`, `silver.ref_tissue`.

⚠️ Do **not** enforce `tissue → diagnosis` as a constraint. It holds in this synthetic
sample but is **not a real-world invariant** (lung tissue yields squamous, small-cell and
other diagnoses). Recognising which observed dependencies are genuine is the judgment
being assessed.

---

## 5. Gold layer — RESOLVED

### 5.1 The core idea: purpose-scoped completeness contracts

This is the author's design contribution, and it is a genuine improvement on the naive
reading of the brief. Stated precisely:

> **A record is never globally "bad." It is complete *for a purpose*, or it is not.**
>
> Completeness is therefore not a property of the data — it is a property of the
> **contract between the data and a question.** The same `silver` row may satisfy the
> contract for mart A and fail it for mart B, and both facts are recorded.

Why this is the right call, and worth arguing explicitly in the submission README:

- A record missing `tumor_purity` is **useless** for a purity-adjusted clonality analysis
  and **perfectly valid** for a gene-recurrence count. Enforcing one global completeness
  rule must therefore either discard usable signal or admit unusable rows. Both are wrong.
- It gives the **NL assistant** exactly what it needs: a mart with a *guaranteed* schema
  where required columns are never NULL, so it never has to reason about missingness and
  never silently returns a wrong count.
- It makes quarantine **informative rather than punitive**: the quarantine sibling of a
  mart is a curated list of "records that nearly qualified, and precisely why" — often
  the most scientifically interesting rows in the dataset.

Every gold mart is therefore defined by a declarative contract:

```yaml
# config/gold_contracts/gold_variant_validated_calls_v1.yaml
mart: gold_variant_validated_calls_v1
schema: gold_open
grain: one row per (sample_id, chrom, pos, ref, alt)
purpose: >
  Validating research outcomes against variant-level evidence. Every row has
  complete call evidence and complete sample context.
required_columns:      # NULL here ⇒ row is quarantined, not loaded
  - sample_id
  - chrom
  - pos
  - ref
  - alt
  - gene_symbol
  - consequence
  - impact
  - vaf
  - depth
  - filter_status
  - tissue
  - disease_group
optional_columns:      # NULL permitted, present for signal
  - tumor_purity
  - ccf
  - gnomad_af_popmax
  - hgvsp
  - mane_select
filters:
  - filter_status = 'PASS'
privacy:
  quasi_identifier_policy: generalise   # see §6
```

### 5.2 Naming convention — RESOLVED

```
<schema>.<zone>_<subject>_<purpose>_v<major>
<schema>.<zone>_<subject>_<purpose>_quarantine_v<major>
```

| Component | Rule | Values here |
|---|---|---|
| `schema` | **Access tier.** The unit of `GRANT`, and the unit of an S3 prefix + IAM policy in production. | `gold_open` (de-identified, broad) · `gold_restricted` (full fidelity, narrow) |
| `zone` | Always `gold` | — |
| `subject` | The primary entity | `variant`, `sample`, `cohort`, `patient` |
| `purpose` | Snake-case, names the **question**, not the technique | `validated_calls`, `gene_burden`, `clinical_profile` |
| `_quarantine` | Suffix marking the rejected sibling of a mart | — |
| `v<major>` | Contract version. **A changed contract makes a new `v2` mart; the `v1` mart keeps working.** | `v1` |

**Why the version is in the name:** it is the same additive-evolution principle applied
one layer up. Tightening a completeness contract would silently change row counts for
every existing consumer — including an NL assistant whose answers would quietly shift.
A new version leaves `v1` intact and lets consumers migrate deliberately.

**Why access tier is the schema, not a name suffix:** `GRANT SELECT ON SCHEMA gold_open
TO researcher_role` is one statement covering every current and future mart in that tier.
A naming suffix requires remembering to apply a grant per table — and the day someone
forgets is a data breach.

### 5.3 Marts for this assignment

Three, chosen to cover the brief's required query shapes (§ "Query": one joining variants
to sample metadata, one aggregating across the cohort):

| Mart | Grain | Purpose | Answers |
|---|---|---|---|
| `gold_open.gold_variant_validated_calls_v1` | one row per (sample, variant) | Research-outcome validation on complete variant evidence joined to sample context | *"Which samples carry a HIGH-impact variant in `TP53`, and what tissue are they from?"* — the **join** requirement |
| `gold_open.gold_cohort_gene_burden_v1` | one row per (gene, disease_group) | Cohort-level recurrence | *"How many variants per gene, and how many distinct patients carry each?"* — the **aggregate** requirement |
| `gold_restricted.gold_sample_clinical_profile_v1` | one row per sample | Sample-level clinical context with full-fidelity dates and purity | Clinical correlation work requiring exact dates — **restricted tier** |

Each ships with its `_quarantine_v1` sibling.

⚠️ On `gold_cohort_gene_burden_v1`: it must expose **both** `n_variants` and
`n_distinct_patients`, never a single ambiguous "count." `P-0003` contributes two samples
(v1 §3.2 M6), so sample-count and patient-count diverge — and an NL assistant asked "how
many patients have a `KRAS` mutation?" must find a column that means exactly that. **A
column named `count` in a cohort mart is a bug**, because it forces the consumer to guess
the denominator.

### 5.4 Per-mart quarantine

Every mart has a sibling table with the mart's columns **plus**:

| Column | Meaning |
|---|---|
| `exclusion_reason_code` | Machine-readable, e.g. `MISSING_REQUIRED_COLUMN`, `FAILED_FILTER_PREDICATE` |
| `exclusion_detail` | Human-readable, e.g. `"required column 'vaf' is NULL"` |
| `missing_columns` | `LIST(VARCHAR)` — exactly which required columns were absent |
| `excluded_at_utc` | `TIMESTAMPTZ` |
| `contract_version` | Which contract version rejected it |

⚠️ **This must be documented prominently:** a record in `gold_X_quarantine_v1` is **not
bad data**. It is data that did not meet *mart X's* contract. The same record may be
present and valid in mart Y. Without this stated, a reader will reasonably assume
quarantine means "corrupt," which inverts the entire design intent.

### 5.5 Reconciliation invariants

Asserted by tests; failure aborts the run:

```
bronze:  source_lines_read          = bronze_rows + bronze_quarantine_rows
silver:  bronze_rows                = silver_rows + silver_quarantine_rows
gold_X:  silver_eligible_rows(X)    = gold_X_rows + gold_X_quarantine_rows
```

Nothing enters a layer and vanishes. This single property is what lets a researcher —
or an agent — trust a count without asking the author.

---

## 6. Governance and access

### 6.1 De-identification policy per tier

Applying v1 §4's quantified finding: **exact `collection_date` alone takes the cohort
from 15% to 100% uniquely-identifiable.**

| Control | `gold_open` | `gold_restricted` |
|---|---|---|
| `collection_date` | **Generalised to month** (`2026-01`) | Exact date |
| `tumor_purity` | Banded (`low` / `medium` / `high`) | Exact value |
| `notes` free text | **Dropped**; only derived flags (`is_ffpe`) survive | Retained |
| `patient_id` | Pseudonym only; linking table absent from this tier | Pseudonym; linking table in a separate fenced zone |
| Access | Broad researcher role | Named individuals, time-boxed, audit-logged |

### 6.2 The honest limitation — state this explicitly

At n=20, **k-anonymity is not achievable by generalisation.** Binning dates to month only
moves 20/20 unique to 9/20 unique (v1 §4). And more fundamentally, **the variant data is
itself an identifier** — on the order of 30–80 common SNPs uniquely identify an individual
and, by extension, their biological relatives. Stripping names from a VCF is not
de-identification in any meaningful sense.

**Therefore: the control is access, not anonymisation.** Do the cheap generalisation
because it costs nothing and removes the easiest attacks; then be explicit that residual
re-identification risk is managed by *who may query*, enforced per zone and audited —
not by any claim that the data is anonymous. Claiming otherwise would be the actual
governance failure.

### 6.3 Production S3-to-S3 mapping

The local directory layout **is** the prefix layout, which is what makes this concrete:

| Zone | S3 prefix | Access |
|---|---|---|
| Landing | `s3://genomics-landing/{batch_id}/` | **Write:** pipeline role only. **Read:** ingestion role only. Object Lock / WORM + versioning. No human access. |
| Bronze | `s3://genomics-bronze/variants/batch_id=.../` | **Write:** ingestion job role. **Read:** platform engineers + silver job. Not researchers. |
| Silver | `s3://genomics-silver/` | **Write:** transform job role. **Read:** data engineering + gold jobs. |
| Gold open | `s3://genomics-gold-open/` | **Read:** broad researcher role. Query via Athena/DuckDB. |
| Gold restricted | `s3://genomics-gold-restricted/` | **Read:** named principals, time-boxed grants, CloudTrail data-events on. |

Cross-cutting: SSE-KMS with a distinct CMK per tier (so key policy is a second
independent control); VPC endpoints with `aws:SourceVpce` conditions; `s3:ObjectCreated:*`
event-driven ingestion rather than polling; every zone versioned so a bad run is
recoverable.

**The single most important property:** each transition is a **separate IAM role that can
read exactly one zone and write exactly one zone.** No principal can read landing and
write gold. That is what makes the pipeline auditable rather than merely functional.

### 6.4 What an NL assistant needs documented

The brief ties assistant reliability directly to this foundation. Deliverables:

1. **Column-level comments in DuckDB** (`COMMENT ON COLUMN`) — the assistant reads the
   catalog, not the README.
2. **A machine-readable data dictionary** per mart: grain, required columns, controlled
   vocabularies with their full value sets, units, and the mart's declared purpose.
3. **Explicit grain statements** — the top cause of wrong LLM SQL is aggregating across
   the wrong grain.
4. **Denominator-safe column names** — `n_variants` / `n_distinct_patients`, never `count`.
5. **The quarantine semantics note from §5.4** — otherwise the assistant will report
   quarantined records as data-quality failures.

---

## 7. Idempotency — RESOLVED (D3)

**Mechanism: partition-level atomic replace, keyed on `batch_id`.**

```
1. write to  warehouse/bronze/variants/_staging/{ingest_run_id}/
2. validate  (reconciliation invariants, row counts, schema check)
3. atomically swap into  batch_id={batch}/   — replacing the partition wholesale
4. record the run in  bronze.file_manifest  (checksums, counts, status)
```

**Why partition-replace rather than merge/upsert:**

- A batch is **immutable by nature** — a sequencing run does not change after the fact.
  Re-running means "reprocess this drop," not "apply deltas."
- It is trivially correct. Merge logic requires a natural key that is stable and unique;
  the `S-0011` conflict demonstrates the source cannot always supply one.
- It makes re-running after a *code* change correct too — a parser bugfix reprocesses the
  batch and replaces it, rather than leaving a mix of old and new rows.

**Skip-if-unchanged:** the SHA-256 of every source file is recorded in
`bronze.file_manifest`. A re-run whose checksums match the last successful run for that
batch is a no-op unless `--force` is passed. This makes `make run` twice genuinely free,
which is what the brief is testing.

Silver and gold are **fully derived and rebuilt** from bronze on each run. At this scale
full rebuild is instant, deterministic, and removes an entire class of incremental-state
bugs. ⚠️ At 1000× this becomes the first thing to change — see §9.

---

## 8. Open questions

| ID | Question | Notes |
|---|---|---|
| **O1** | Multi-sample VCFs | These files carry exactly one sample column each, making `bronze.variants` grain unambiguous. Production VCFs are frequently multi-sample (tumour/normal pairs especially). Parse the sample columns from the `#CHROM` header rather than assuming column 10 is the only one — cheap now, structural later. |
| **O2** | Variant normalisation | No multi-allelic sites and no left-alignment issues in this data (v1 §3.3 V9). Real data needs `bcftools norm`. **Named as the first thing that breaks at scale.** |
| **O3** | `MAX_POP_AF` vs `GNOMAD_AF_POPMAX` | They disagree on 83/296 batch-2 rows (v1 §3.3 V7) — different measurements, not a rename. Both promoted as separate typed columns. Which one a mart should *use* is a scientific question for the researcher, not a modelling decision. Document, do not choose. |
| **O4** | Non-PASS calls in gold | `gold_variant_validated_calls_v1` filters to `PASS`. The 123 non-PASS calls remain fully available in silver. Confirm no mart needs them. |
| **O5** | Testing depth | Proposed: unit tests on the parsers (Flag INFO fields, `CSQ` format-string drift, `.`→NULL, `%`→fraction), plus one end-to-end idempotency test asserting run-twice equality, plus the reconciliation invariants as assertions. |

---

## 9. Non-goals — stated deliberately

- **No imputation of missing clinical values.** A deliberate non-action; NULL is honest.
- **No LLM in the pipeline execution path** (§4.4).
- **No handling built *for* the malformed file** — detection, quarantine, and a written
  production approach, per the brief's explicit instruction.
- **No variant normalisation / multi-allelic splitting** (O2).
- **No cloud infrastructure.** Everything runs locally from a clean checkout.
- **No incremental silver/gold.** Full rebuild, justified by scale, flagged as the first
  thing to change at 1000×.

### What changes at 1000×

1. Full rebuild of silver/gold becomes untenable → incremental, batch-scoped merges.
2. Single-node DuckDB stops being enough for gold → the same Parquet + contracts run on
   Athena/Spark/Trino unchanged, which is a deliberate benefit of keeping bronze as open
   Parquet rather than a proprietary format.
3. Bronze partitioning may need a second dimension (chromosome) — **only** once a single
   batch partition exceeds ~1 GB (§3.5).
4. `raw_line` retention becomes a cost decision — likely tiered to Glacier after N days.
5. Table format upgrade (Iceberg / Delta) for atomic multi-partition commits, time travel
   and schema-evolution metadata that plain Parquet directories cannot provide.

---

## 10. AI assistance log — running

| Area | Use | Trust posture |
|---|---|---|
| Landing-zone profiling (v1 §3) | AI ran the shell/Python passes enumerating every defect | **Verified** — each finding reproducible by command; spot-checked by hand against raw files |
| Re-identification counts (v1 §4) | AI wrote and ran the k-anonymity computation | **Verified** — arithmetic re-checked; cohort small enough to confirm by inspection |
| Terminology | AI supplied vocabulary (quasi-identifier, k-anonymity, functional dependency) | Accepted after independently confirming definitions |
| Architecture (this document) | AI drafted layer specs from author's stated design | **Author-directed.** Medallion adoption, quarantine philosophy, and the purpose-scoped gold contract are the author's decisions. |
| Corrections accepted | Parquet schema-strictness; `DATE` vs `TIMESTAMPTZ`; LLM out of execution path | Each independently reasoned before adoption — see the ⚠️ markers |
| **Not trusted** | Initial AI framing that Parquet was unsuitable for a flexible bronze layer was **wrong** and was corrected by checking `union_by_name` semantics directly | Recorded because the brief asks where AI was not trusted |

---

## 11. Changelog

**v2 (2026-08-23)** — Architecture resolved.

- **D1 RESOLVED:** medallion — Parquet bronze, DuckDB silver, DuckDB gold marts.
- **D2 RESOLVED:** typed core + `MAP` in bronze; conformed relational silver; narrow
  purpose-built gold marts. Drift absorbed via `union_by_name`.
- **D3 RESOLVED:** partition-level atomic replace on `batch_id`, checksum-gated.
- **D4 RESOLVED:** three-tier defect granularity, extended with **purpose-scoped
  quarantine** in gold.
- **New:** gold naming convention (§5.2); access tier as schema; contract versioning.
- **New:** `bronze.vcf_headers` and `bronze.file_manifest` datasets, making schema drift
  and file integrity queryable.
- **Refined from v1:** `S-0020` now lands its valid rows in bronze with a file-level
  truncation verdict, and is excluded at *silver* rather than quarantined at bronze —
  preserving raw evidence while keeping the v1 outcome (missing, never zero).
- **Corrections to stated intent (⚠️):** `.`→NULL is a mandatory bronze conversion;
  `collection_date` is `DATE` not UTC `TIMESTAMPTZ`; vocabulary agent moves to the
  authoring loop, not the execution path.
- **Still open:** O1–O5 (§8).
