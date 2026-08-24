# Initial Data Layer — Working Context v1

| | |
|---|---|
| **Version** | v1 |
| **Created** | 2026-08-22 (UTC) |
| **Status** | 🟡 **PROBLEM FRAMING** — no architecture decision is final |
| **Supersedes** | — (initial version) |

---

## 0. How to use this document

This is the authoritative context for the project. `AGENTS.md` holds stable operating
rules; **this file holds everything that is still moving.** It is append-only — to
revise it, write `v2` rather than editing this file.

Sections marked **VERIFIED** are facts established by running commands against the data.
Sections marked **DRAFT** or **PROPOSED** are thinking in progress and may be wrong.
Sections marked **OPEN** are decisions not yet made.

---

## 1. Problem statement — DRAFT

> Somatic variant calls and their sample metadata arrive from a sequencing pipeline as
> per-batch drops into an immutable landing zone. The drops are **messy** (inconsistent
> encodings, conflicting duplicates, missing values, referential gaps) and their
> **shape changes over time** without warning as the pipeline is versioned. Researchers
> need to query this data with confidence, and a natural-language assistant will later
> answer questions on top of it without a human in the loop to sanity-check its SQL.
>
> Build the first slice of a foundation that makes that trustworthy: a re-runnable
> ingestion path from landing to a governed curated zone, a schema whose grain is
> explicit, and documentation strong enough that a researcher — or an agent — can rely
> on the data without asking the author what a column means.

### The constraint that shapes every decision

There are **two consumers with opposing preferences**, and the design must serve both:

| Consumer | Wants |
|---|---|
| **SQL researcher, today** | Flexibility. All the raw detail. Ability to reach fields the modeller didn't anticipate. |
| **NL assistant, later** | Rigidity. A small, stable, well-named, fully-documented surface with no ambiguity about which column answers which question. |

An assistant cannot write correct SQL against a schema whose columns it must guess at.
This tension is the substance of Open Decision **D2** below, and most of the rest
follows from how it is resolved.

---

## 2. What the exercise is actually testing — DRAFT

Read closely, the brief is unusually explicit about its own rubric:

- *"We care about judgment, clarity, and robustness far more than completeness."*
- *"Better to do less, well-reasoned and documented, than to gold-plate."*
- *"We're at least as interested in how you reason, in the README, as in what you finish."*

**Inference:** the code is small and most of the score lives in the written reasoning.
The dataset has been deliberately seeded with defects that each have an obvious naive
handling and a defensible considered handling. The test is whether the candidate
*notices* them, makes a call, and **writes down why**.

A secondary inference: the brief mentions the future NL assistant twice, unprompted, and
ties data quality directly to assistant reliability. That is not framing — it is the
thing they care about. Schema decisions should be argued in those terms.

---

## 3. Landing zone profile — VERIFIED

All findings below were established by running commands against `candidate_bundle/data/`.

### 3.1 Inventory

| | batch_2026_01 | batch_2026_02 |
|---|---|---|
| VCF files | 14 | 5 |
| Manifest rows (excl. header) | 15 | 5 |
| Distinct `sample_id` in manifest | 14 | 5 |
| Variant rows across VCFs | ~794 | ~296 |
| Pipeline version (`##source`) | `SyntheticPipeline_v1.4` | `SyntheticPipeline_v1.5` |
| Reference | GRCh38 | GRCh38 |

Total cohort: **20 samples, 20 patients, ~1090 variant rows.** Small enough to inspect
exhaustively; must be treated as representative of something orders of magnitude larger.

### 3.2 Manifest defects — VERIFIED

| ID | Defect | Naive handling | Why it is a trap |
|---|---|---|---|
| M1 | `collection_date` in **5 formats**: `Jan 5 2026`, `2026-01-07`, `2026/01/09`, `17/01/2026`, and empty | `pd.to_datetime(infer=True)` | `04/01/2026` (S-0013) is genuinely ambiguous — Apr 1 or Jan 4? The batch is `batch_2026_01`, so **DD/MM is the only reading consistent with the batch window.** This is an inference and must be stated as one. |
| M2 | `tumor_purity` in **mixed units**: `0.32` vs `63%` vs empty | `float(x)` | Raises on `63%`. Worse, a naive strip-and-cast yields `63.0` — a purity of 6300%. |
| M3 | **`S-0011` appears twice**, identical except `tumor_purity` = `57%` vs `0.64` | `drop_duplicates()` | Not an exact duplicate — the rows **conflict**, and there is no ingestion timestamp or row version to justify picking a winner. |
| M4 | **`S-0008` is in the manifest but has no VCF file** | ignore it | Referential integrity gap. The real-world cause is a file that failed to land, which is an operational incident, not a no-op. |
| M5 | `S-0007`: `sex_reported=Female` but `sex_inferred=M` | normalise both, move on | A genuine **discordance** — the canonical signal of a sample swap or mislabel. A real QC finding. Must never be silently reconciled. |
| M6 | `P-0003` has **two samples** (S-0003, S-0004) | assume sample == patient | Proves patient is a real grain above sample. Any cohort count must declare whether its denominator is samples or patients. |
| M7 | `qc_status` empty for S-0012, S-0014 | treat as PASS | A sample with no QC verdict is not a passing sample. |
| M8 | `tissue` = `" Lung"` / `"LUNG "` / `"lung"`; platform spelled 4 ways for 2 real instruments | `.strip().lower()` | Adequate for cleaning, **inadequate for the assistant** — it needs a controlled vocabulary, not merely consistent strings. |
| M9 | `notes` free text: `FFPE block`, `repeat library` | keep as text | `FFPE` is clinically meaningful (fixation causes characteristic C>T artefacts). Arguably a typed flag, not prose. |
| M10 | batch 2 adds column `library_prep`, itself inconsistent (`TruSeq DNA PCR-Free` vs `truseq dna pcr-free`) | — | The manifest-side schema drift. |

### 3.3 VCF structure and drift — VERIFIED

| ID | Finding |
|---|---|
| V1 | `HOTSPOT` is a **Flag** — appears bare, with no `=value`. Naive `k, v = field.split("=")` raises on every hotspot row (50 in batch 1, 23 in batch 2). |
| V2 | `QUAL` is `.` in **361 of 1090 rows**. Null, not zero. |
| V3 | **123 non-PASS calls** across 4 FILTER values (`low_depth`, `weak_evidence`, `germline_risk`). Dropping them destroys the researcher's ability to change the threshold later. |
| V4 | **Contig header lists differ per file** — S-0001 declares no chr8/15/20/22/X. Headers describe the file, not the reference. Not authoritative for validation. |
| V5 | Batch 2 adds INFO fields **`CCF`** (cancer cell fraction) and **`GNOMAD_AF_POPMAX`**. |
| V6 | **`CSQ` grows from 6 to 7 pipe sub-fields** in batch 2 (`MANE_SELECT` appended). The sub-field order is declared in the `##INFO=<ID=CSQ...Format: ...>` header line. A parser that hardcodes positions survives *this* change only by luck — the exercise is testing whether the format string is parsed. |
| V7 | `MAX_POP_AF` and `GNOMAD_AF_POPMAX` **disagree on 83 of 296 batch-2 rows.** They are different measurements, not a rename. Collapsing them would be a data-integrity bug. |
| V8 | Genotype fields are internally consistent — `AD` sums to `DP` in every valid row. No cleaning needed there. |
| V9 | No multi-allelic sites (no commas in `ALT`). Simplifies the variant key; **note this as an assumption that will not hold at scale.** |

### 3.4 The malformed file — VERIFIED

**`batch_2026_02/S-0020.somatic.vcf` is truncated.** The file ends **mid-line, mid-`CSQ`
string, with no trailing newline**; line 101 carries 8 tab-separated fields instead of 10.

This is not a bad *value* — it is a **partial write**, the signature of an interrupted
transfer or an incomplete S3 multipart upload.

**The trap:** the first 100 rows of the file are perfectly valid. The tempting handling
is to load the 100 good rows and skip the bad one.

**That is the wrong call, and this is probably the single most important paragraph in
the eventual submission README.** Truncation is unbounded — you cannot know whether it
lost 1 variant or 500. A partial load therefore **silently understates that sample's
mutation burden**, and every cohort aggregate including S-0020 becomes quietly wrong with
no error surfaced anywhere. In oncology that is not a rounding error; tumour mutational
burden is a treatment-selection input.

**Correct handling: quarantine the whole file, fail loudly, and count the sample as
_missing_ rather than as _zero_.** The distinction between "no data" and "no variants" is
the difference between an honest gap and a false negative.

---

## 4. Re-identification analysis — VERIFIED

Computed over all 20 unique samples (S-0011 de-duplicated for this purpose):

| Quasi-identifier set | Samples uniquely identified (k=1) |
|---|---|
| `tissue` + `sex` | 3 / 20 (15%) |
| `tissue` + `sex` + `disease_group` | 3 / 20 (15%) |
| **`tissue` + `sex` + exact `collection_date`** | **20 / 20 (100%)** |
| `diagnosis` + `sex` + `collection_date` + `platform` | 20 / 20 (100%) |

**The collection date single-handedly destroys anonymity** — it moves the cohort from
15% uniquely-identifiable to 100%, because each sample carries its own date.

Generalising the date to **month** improves this only to **9 / 20 still unique (45%)**.

### What follows from that

At n=20, **k-anonymity is not achievable by generalisation at any acceptable cost.** And
the deeper point specific to this domain: **the variant data is itself an identifier** —
on the order of 30–80 common SNPs uniquely identify an individual, and by extension their
biological relatives. Stripping names from a VCF is not de-identification in any
meaningful sense.

**Therefore the control is access, not anonymisation.** The defensible position:

- Do the cheap generalisation anyway (bin dates to month; drop or type the free-text
  `notes`; keep `patient_id` as a pseudonym with the linking table in a separately
  fenced zone).
- Then state honestly that residual re-identification risk is managed by **who is
  permitted to query**, enforced per zone, and audited — not by a claim that the data is
  anonymous.

Relevant terminology, for the write-up: these fields are **quasi-identifiers**; the
attack is an **inference attack** / attribute disclosure; the metric is **k-anonymity**.
Distinct from **imputation** (statistically filling a missing value) and **functional
dependency** (`diagnosis → disease_group` holds strictly here, which is why
`disease_group` is derived reference data rather than a per-sample attribute).

⚠️ Note that `tissue → diagnosis` *also* holds in this synthetic sample but is **not a
real-world invariant** — lung tissue yields squamous, small-cell and other diagnoses.
Do not enforce it as a constraint. Recognising which observed dependencies are real and
which are artefacts of a small sample is exactly the judgment being graded.

---

## 5. Working principles — PROPOSED

1. **Quarantine, never drop; quarantine, never impute.** Both drop and impute lose
   information silently. Rejected records go to a quarantine table with a reason code and
   full source coordinates. `rows_read = rows_loaded + rows_quarantined` must hold and
   should be asserted.
2. **Defects have tiers** (see D4) — the response to a missing optional value is not the
   response to a structurally broken file.
3. **Parse declared contracts at runtime.** VCF headers declare their own schema; use it.
4. **Provenance on every row.** Source file, batch, pipeline version, ingestion run id.
   `##source` moving v1.4 → v1.5 is what *explains* the schema drift; that link should be
   queryable, not folklore.
5. **Document decisions where the consumer will look**, not only in the README — the NL
   assistant will read column comments and a data dictionary, not prose.

---

## 6. Open decisions register — OPEN

### D1 — Storage engine and zone layout · **OPEN**

Options: DuckDB over partitioned Parquet · single DuckDB file · SQLite.

Leaning toward **DuckDB over Parquet**, because it makes the required "landing → curated,
S3-to-S3, each zone fenced" narrative *literal* — the curated directory is the prefix
layout, and access control becomes a real per-prefix boundary rather than a hand-wave.
Not settled; partly falls out of D2.

### D2 — Schema shape, grain, and where drifted fields live · **OPEN — the important one**

Where do batch 2's new INFO fields go?

| Option | For | Against |
|---|---|---|
| New nullable typed columns | Best for SQL and for the assistant; fully typed | Requires a migration per drift event; unbounded column growth |
| Semi-structured `MAP`/`JSON` column | Absorbs any drift with zero migration | **Opaque to an NL assistant** — it cannot know the keys exist |
| Tall key-value table | Infinitely flexible | Every query needs a pivot; hostile to both consumers |

Likely resolution is a **hybrid**: typed columns for the stable VCF core plus a
semi-structured column for the open-ended INFO dictionary, with a **promotion path** —
an INFO key that proves stable and useful is promoted to a typed column in the curated
layer while remaining in the map for lineage. Needs to be worked through properly.

Also unresolved within D2: the table set and the declared **grain** of each
(variant-per-sample? variant-per-sample-per-transcript-annotation? sample? patient?).
The `CSQ` field is one annotation per row here, but VEP output is generally one row *per
transcript*, which would change the grain — worth deciding deliberately rather than
inheriting from the sample data.

### D3 — Idempotency mechanism · **OPEN**

Options: partition overwrite (delete-and-replace by batch) · merge/upsert on a natural
key · content-hash dedup. Interacts with D1.

### D4 — Conflict and defect policy · **OPEN, but a shape is emerging**

One consistent, documented rule beats five ad-hoc ones. Proposed three tiers:

| Tier | Defect | Response |
|---|---|---|
| **Value-level** | missing optional value (`tumor_purity` for S-0003, empty `qc_status`) | **Load the row, leave NULL.** Never drop a whole sample — and its 50+ valid variants — because one optional attribute is absent. |
| **Record-level** | conflicting duplicate (M3, S-0011), referential gap (M4, S-0008), field discordance (M5, S-0007) | **Load nothing ambiguous; quarantine with a reason code and surface it.** Do not pick a winner without a rule that can be justified. |
| **File-level** | structural corruption (S-0020 truncation) | **Quarantine the entire file.** Never partially load a structurally unsound file. |

---

## 7. Non-goals — DRAFT

Deliberate exclusions, to be stated explicitly in the submission README:

- No imputation of missing clinical values (see §5.1 — a deliberate non-action).
- No handling built *for* the malformed file; detection and quarantine only, with the
  production approach described in prose, per the brief's instruction.
- No multi-allelic splitting or variant normalisation (left-alignment / trimming) — not
  needed for this data (V9), but **named as the first thing that breaks at scale.**
- No cloud infrastructure, per the brief.

---

## 8. AI assistance log — running

The brief requires a note on how AI tooling was used and where it was not trusted.
Accumulate entries here as work proceeds.

| Area | Use | Trust posture |
|---|---|---|
| Landing-zone profiling | AI ran the shell/Python passes that enumerated §3 defects | **Verified** — every finding is reproducible by a command; spot-checked against the raw files by hand |
| Re-identification counts (§4) | AI wrote and ran the k-anonymity computation | **Verified** — arithmetic re-checked; small enough to confirm by inspection |
| Terminology and framing | AI supplied vocabulary (quasi-identifier, k-anonymity, functional dependency) | Accepted, but definitions independently confirmed before use |

---

## 9. Changelog

**v1 (2026-08-22)** — Initial context. Landing zone fully profiled and defects
enumerated (§3). Re-identification risk quantified (§4). Four open decisions registered
(§6); none resolved. No architecture chosen, no code written.
