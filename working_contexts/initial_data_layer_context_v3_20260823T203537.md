# Initial Data Layer — Working Context v3

| | |
|---|---|
| **Version** | v3 |
| **Created** | 2026-08-23 |
| **Status** | 🟢 **ARCHITECTURE RESOLVED** — unchanged from v2; implementation not started |
| **Supersedes** | `initial_data_layer_context_v2_20260823T233743Z.md` |

---

## 0. How to use this document

**Nothing about the architecture changed in this version.** v2 (§1–§11) is fully valid
and is the authoritative content — read it for the medallion design, bronze/silver/gold
specs, governance and open questions. This file exists only to record one **meta / tooling
decision**: a correction to how working-context files themselves are timestamped.

---

## 1. What changed — the context-file naming convention

`AGENTS.md` §0 previously required the working-context filename to carry a `Z`-suffixed
**UTC** timestamp (`YYYYMMDDTHHMMSSZ`), e.g. `..._v2_20260823T233743Z.md`.

**Dropped.** The `Z` / UTC claim is gone. The filename now carries a plain local
timestamp, `YYYYMMDDTHHMMSS`, taken verbatim from `date +%Y%m%dT%H%M%S` — no timezone
suffix asserted.

### Why

An agent asserting `Z` on a timestamp is claiming it converted its system clock to UTC.
It generally has not — it is guessing or copying the local clock's digits and appending
`Z` as decoration. That is a **fabricated fact** sitting in a filename inside an
append-only decision log, in a project whose entire thesis is that an NL assistant (and,
by extension, anything reading this repo's own metadata) must not be handed
unverifiable claims dressed up as verified ones. Keeping a false precision marker here
would be the same category of error this project spends v1–v2 arguing against in the
data itself (see v2 §4.3 — a related but distinct point about `collection_date`, where
the fix was "don't invent a timezone for an event that has none"; here the fix is "don't
invent a timezone label for a timestamp whose zone was never actually checked").

### What this does *not* touch

This is purely about the **working-context filename's** timestamp suffix. It does **not**
reopen v2 §4.3 (`collection_date` is `DATE`, no zone; system timestamps like
`ingested_at_utc` are `TIMESTAMPTZ`, UTC) — that decision concerns pipeline data and
remains RESOLVED, unchanged, and is a genuinely different question: there, the system
*does* generate the timestamp itself and *can* correctly stamp it UTC; here, the agent
authoring a context file has no verified clock at all, so asserting a zone would be the
fabrication `AGENTS.md` §0 now explicitly forbids.

### The rule as it now reads (`AGENTS.md` §0)

```
working_contexts/initial_data_layer_context_v<N>_<timestamp>.md
                                              │     └── YYYYMMDDTHHMMSS, from
                                              │        `date +%Y%m%dT%H%M%S` — run, not guessed
                                              └── integer, monotonically increasing
```

`v<N>` remains the real tie-break for "which context is current" (`AGENTS.md` §0 step 2);
the timestamp is provenance only, never the sort key. Existing `v1`/`v2` filenames with
the old `Z` suffix are left as-is — append-only history is not rewritten retroactively.

---

## 2. AI assistance log addendum

| Area | Use | Trust posture |
|---|---|---|
| Naming-convention fix (this version) | User-directed: identified the UTC-suffix requirement as risky, asked for it dropped | Author-directed; AI applied the change to `AGENTS.md` and recorded the reasoning here |

---

## 3. Changelog

**v3 (2026-08-23)** — Meta-only naming fix, plus a detailed bronze-layer implementation
plan.

- Dropped the `Z`/UTC timestamp requirement from the `working_contexts/` filename
  convention in `AGENTS.md` §0, replacing it with a plain local timestamp — an agent
  cannot truthfully assert a timezone it never converted to. Existing `v1`/`v2`
  filenames left untouched.
- Added §4, **Implementation plan**: one plan, not three — bronze is broken into
  sequenced, independently-acceptance-tested tasks (BR-1..BR-8) ready to hand to an
  execution workflow; silver gets a readiness checklist against bronze's planned
  output, not a task breakdown yet; gold is explicitly deferred, untouched.

---

## 4. Implementation plan

### 4.0 Scope and how to use this section

One plan, not three separate ones per layer — bronze is the only layer being built this
pass, so it is the only layer broken into executable tasks. Silver gets a **readiness
checklist**: what bronze's output must guarantee before silver can be written against
it, re-derived from v2 §4, not a task list — sequencing silver's own task breakdown
*after* bronze ships means it gets written against bronze's actual schema instead of its
planned one. Gold is untouched this pass; v2 §5 remains the target design.

Each bronze task below states **Goal / Reads / Writes / Steps / Done when / Depends on**
so it can be handed to an execution workflow one task at a time, in order — a task
should not start before the tasks it depends on are marked done, and "Done when" is
meant to be checked mechanically (a command that passes or fails), not judged by eye.

All source facts referenced below (VCF header declarations, manifest columns, the two
known defects) were re-confirmed against the actual files in this session
(`grep -E '^##'`, `grep -E '^#CHROM'` against `S-0001.somatic.vcf` and the drifted
`S-0016.somatic.vcf`) — not carried over from v1/v2 by assumption.

### 4.1 Storage root and directory contract

Applies to all three layers; only bronze is populated this pass.

```
inocras_datalayers/
├── candidate_bundle/data/          SOURCE — immutable, read-only, never written to
└── warehouse/                      NEW — sibling of candidate_bundle/, gitignored
    ├── bronze/
    │   ├── variants/batch_id=<batch>/part-00000.parquet
    │   ├── sample_manifest/batch_id=<batch>/part-00000.parquet
    │   ├── vcf_headers/batch_id=<batch>/part-00000.parquet
    │   ├── file_manifest/batch_id=<batch>/part-00000.parquet
    │   ├── _quarantine/batch_id=<batch>/part-00000.parquet
    │   └── _staging/<ingest_run_id>/...           transient, swapped into place, then removed
    ├── silver.duckdb                              not created this pass
    └── gold.duckdb                                not created this pass
```

- `warehouse/` is created by `data_loader` itself on first run (`mkdir -p` semantics) —
  never a manual setup step, per the "clean checkout + one command" reproducibility
  rule (`AGENTS.md` §3 hard rule 7).
- Add `warehouse/` to `.gitignore` as part of task **BR-1**.
- Naming note: the source is `candidate_bundle/data/`; the output root is `warehouse/`,
  never `data/` — two directories both named `data` in the same repo, one immutable
  source and one generated output, is exactly the kind of ambiguity this project argues
  against elsewhere. `warehouse/` also matches the name already resolved in v2 §2/§3.5.

### 4.2 `data_loader` — bronze layer CLI

#### 4.2.1 Module layout

```
data_loader/
├── __init__.py
├── __main__.py            entry point — `python -m data_loader <batch_id>`
├── cli.py                 argparse: positional batch_id, --force, --data-root, --out-root
├── vcf_headers.py          BR-2: parse ##INFO/##FORMAT/##FILTER/##contig/##source/... + CSQ Format string
├── vcf_rows.py             BR-3: parse data lines using the per-file contract from vcf_headers.py
├── manifest.py             BR-4: parse sample_manifest.csv structurally
├── integrity.py            BR-5: per-file size/sha256/row-count/truncation checks
├── writer.py               BR-6: DuckDB COPY TO parquet, staged + atomic swap per batch_id
├── run.py                  BR-7/BR-8: orchestration, reconciliation check, skip-if-unchanged, summary
└── models.py               shared row/record dataclasses (quarantine record, file_manifest record, etc.)
```

Also add to `pyproject.toml`:

```toml
[project]
dependencies = ["duckdb"]

[project.scripts]
data-loader = "data_loader.cli:main"
```

`duckdb` is the only new dependency — it both writes the Parquet output (`COPY ... TO
... (FORMAT parquet, COMPRESSION zstd)`) and will be silver/gold's engine later (v2 §1
D1), so bronze does not introduce a second Parquet library. VCF and CSV parsing use the
stdlib (`csv`, plain text) — no new dependency needed for either, and per the working
agreement (`AGENTS.md` §5) a dependency the author hasn't used is itself a cost to
avoid unless it earns its place.

#### 4.2.2 CLI contract

```
uv run data-loader <batch_id> [--force] [--data-root PATH] [--out-root PATH]
```

| Arg | Meaning | Default |
|---|---|---|
| `batch_id` (positional, required) | e.g. `batch_2026_01` — resolved to `<data-root>/<batch_id>/` | — |
| `--force` | reprocess even if file checksums match the last recorded run | off |
| `--data-root` | landing zone root | `candidate_bundle/data` |
| `--out-root` | warehouse root | `warehouse` |

**Exit codes:**

| Code | Meaning |
|---|---|
| `0` | Run completed; reconciliation invariant held (bad rows/files are quarantined, not errors) |
| `1` | `<data-root>/<batch_id>/` does not exist, or contains zero files |
| `2` | Reconciliation invariant failed (`rows_read != rows_loaded + rows_quarantined`) — a bug, not a data defect; must never happen in normal operation |

**Stdout, on success:** one summary line per bronze dataset —
`variants: read=450 loaded=447 quarantined=3` etc. — plus the run's `ingest_run_id`.
This is the human-facing half of the reconciliation check in BR-7; the machine-facing
half is the assertion itself.

#### 4.2.3 Bronze dataset schemas (concrete, for the implementer — no re-deriving from prose)

**`bronze.sample_manifest`** — one row per manifest CSV row, **including both `S-0011`
rows** (bronze never deduplicates — v2 §3.6). All columns `VARCHAR`, structural
transforms only (trim, `""`→NULL). Confirmed manifest columns, batch_2026_01 (13 cols):
`sample_id, patient_id, batch_id, collection_date, tissue, diagnosis, disease_group,
tumor_purity, sex_reported, sex_inferred, sequencing_platform, qc_status, notes`.
batch_2026_02 adds a 14th, `library_prep` — read from each file's own header row, never
assumed positionally, so this is additive with zero code change. Plus provenance
columns on every row: `batch_id, source_file, source_line_no, ingest_run_id,
ingested_at_utc`.

**`bronze.variants`** — one row per VCF data line. Confirmed VCF column header (both
batches, identical): `#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT <sample_id>`.
Bronze columns: `chrom, pos, id, ref, alt, qual, filter, info MAP(VARCHAR,VARCHAR),
format_keys LIST(VARCHAR), genotype_values LIST(VARCHAR)` — genotype is kept as the
raw `:`-split FORMAT/sample pair rather than pre-split into `gt/ad/dp/vaf` columns,
because *which* FORMAT keys exist is itself declared per-file (confirmed identical
`GT:AD:DP:VAF` in both batches today, but not guaranteed by contract) — splitting it
into named columns is a silver-layer interpretation, not a bronze structural fact. Plus
provenance: `batch_id, source_file, source_line_no, pipeline_version` (from that file's
`##source`), `ingest_run_id, ingested_at_utc`.

**`bronze.vcf_headers`** — one row per `(source_file, header_type, header_id)`.
Columns: `batch_id, source_file, header_type` (`INFO`/`FORMAT`/`FILTER`/`contig`),
`header_id, number, type, description, ingest_run_id`. Confirmed header IDs present
today — `INFO`: `CALLER, MAX_POP_AF, HOTSPOT, CSQ` (batch_2026_02 additionally `CCF,
GNOMAD_AF_POPMAX`); `FORMAT`: `GT, AD, DP, VAF`; `FILTER`: `PASS, weak_evidence,
low_depth, germline_risk`. The `CSQ` row's `description` carries its own sub-field
order verbatim (`"...Format: SYMBOL|Consequence|IMPACT|HGVSc|HGVSp|EXON"` in batch 1,
with `|MANE_SELECT` appended in batch 2) — `vcf_rows.py` must parse that same string at
row-parse time, not a second hardcoded copy of it.

**`bronze.file_manifest`** — one row per source file (VCF *and* manifest CSV).
Columns: `batch_id, source_file, file_type` (`vcf`/`manifest`), `byte_size, sha256,
row_count, parse_status` (`OK`/`TRUNCATED`/`UNREADABLE`), `is_truncated BOOLEAN,
pipeline_version, reference_genome, file_date, ingest_run_id, ingested_at_utc`.

**`bronze._quarantine`** — one row per record (VCF line or manifest row) that failed
its own file's structural contract. Columns: `batch_id, source_file, source_line_no,
record_type` (`vcf_row`/`manifest_row`), `raw_line, reason_code, reason_detail,
ingest_run_id, ingested_at_utc`.

#### 4.2.4 Task breakdown

**BR-1 — Scaffolding, CLI skeleton, storage root**
- *Reads:* nothing. *Writes:* `data_loader/` package skeleton, `pyproject.toml`
  updates, `.gitignore` entry for `warehouse/`.
- *Steps:* create module layout (4.2.1); wire `argparse` per the CLI contract (4.2.2);
  implement batch-folder resolution + existence check (exit code `1` path); implement
  `warehouse/` directory creation.
- *Done when:* `uv run data-loader batch_2026_01` on an empty `warehouse/` creates the
  full directory tree from 4.1 and exits `0` with an empty summary (no parsing logic
  yet — this task is plumbing only); `uv run data-loader batch_2026_99` (nonexistent)
  exits `1`.
- *Depends on:* nothing.

**BR-2 — VCF header-contract parser**
- *Reads:* one `.somatic.vcf` file's `##` lines. *Writes:* an in-memory contract object
  (INFO/FORMAT/FILTER/contig declarations + parsed `CSQ` sub-field order); no Parquet
  yet.
- *Steps:* parse each `##KEY=<...>` line into `(ID, Number, Type, Description)`;
  specifically extract the `Format: A|B|C...` clause out of the `CSQ` INFO
  `Description` string (confirmed present verbatim in both batches' headers — see
  4.2.3) into an ordered list of sub-field names.
- *Done when:* run against `S-0001.somatic.vcf` (batch 1) yields a `CSQ` order of
  exactly `[SYMBOL, Consequence, IMPACT, HGVSc, HGVSp, EXON]` (6 items); run against
  `S-0016.somatic.vcf` (batch 2) yields the same 6 plus `MANE_SELECT` (7 items) —
  **this is the test that proves the drift is handled by parsing, not by luck.**
- *Depends on:* BR-1.

**BR-3 — VCF row parser**
- *Reads:* a VCF's data lines + that file's contract object from BR-2. *Writes:*
  in-memory `bronze.variants` rows + quarantine records; no Parquet yet.
- *Steps:* split each line on tab; validate field count == `9 + n_sample_columns`
  (from `#CHROM` header); map `.` and `""` → NULL (`QUAL` is `.` in a large fraction of
  rows — confirmed in v1 profiling, re-verify count against this batch's files rather
  than trusting the old number); split `INFO` on `;`, then each `key=value` on `=`
  — **a bare key with no `=` (e.g. `HOTSPOT`, confirmed present in sample data lines
  above) is a Flag and maps to `'true'`, not a parse error**; split `CSQ`'s value on
  `|` using BR-2's declared order for that file, by position count not by name (VCF
  doesn't name sub-fields inline, only in the header); on any field-count mismatch,
  route the whole line to quarantine with `raw_line` and `reason_code =
  'MALFORMED_VCF_LINE'`, and continue to the next line — one bad line never aborts the
  file.
- *Done when:* parsing `S-0001.somatic.vcf` produces zero quarantined rows (it is
  clean) and a `HOTSPOT` row's `info['HOTSPOT']` is `'true'`, not a KeyError or a
  crash; parsing a hand-truncated copy of a valid VCF (one line cut mid-field, used
  only as a test fixture — the real `batch_2026_02/S-0020.somatic.vcf` is not touched
  here per `AGENTS.md` hard rule 1) quarantines exactly the truncated line and still
  parses every line before it.
- *Depends on:* BR-2.

**BR-4 — Manifest parser**
- *Reads:* `sample_manifest.csv`. *Writes:* in-memory `bronze.sample_manifest` rows +
  quarantine records; no Parquet yet.
- *Steps:* read via stdlib `csv.DictReader` (header-driven, so batch 2's extra
  `library_prep` column is picked up with no code change); trim whitespace on every
  field; `""` → NULL; a row whose field count doesn't match that file's header count →
  quarantine with `reason_code = 'MALFORMED_MANIFEST_ROW'`.
- *Done when:* parsing batch_2026_01's manifest yields **16 rows including both
  `S-0011` entries** (bronze does not deduplicate — that is silver's job, v2 §4.5);
  parsing batch_2026_02's manifest yields rows with a populated `library_prep` column
  that batch_2026_01 rows simply don't have.
- *Depends on:* BR-1.

**BR-5 — File-level integrity pass**
- *Reads:* every file in the batch folder (both VCFs and the manifest). *Writes:*
  in-memory `bronze.file_manifest` rows.
- *Steps:* compute byte size + SHA-256 per file; count data rows; check last byte is a
  newline; for VCFs, check every data line's tab-count equals `9 + n_samples` (the
  structural truncation signal from v2 §3.7 detection method 3) and set
  `parse_status='TRUNCATED', is_truncated=true` if any line fails that check *and* it
  is the file's last line (mid-file malformed lines are BR-3's per-row quarantine, not
  a file-level truncation verdict).
- *Done when:* run against `batch_2026_02/S-0020.somatic.vcf` sets
  `is_truncated=true, parse_status='TRUNCATED'` — this is the file the whole
  malformed-file trap is built around (v1 §3.4) — while BR-3 still lands its ~100 valid
  rows from the same file undisturbed.
- *Depends on:* BR-1. (Independent of BR-3/BR-4 — can run in parallel with them.)

**BR-6 — Parquet writer with staged atomic swap**
- *Reads:* the in-memory row sets from BR-3/BR-4/BR-5. *Writes:*
  `warehouse/bronze/**/batch_id=<batch>/part-00000.parquet` for all five datasets.
- *Steps:* write each dataset to
  `warehouse/bronze/<dataset>/_staging/<ingest_run_id>/part-00000.parquet` via DuckDB
  `COPY (SELECT ...) TO '...' (FORMAT parquet, COMPRESSION zstd)`; once all five
  datasets have written successfully, atomically move each staged file into
  `batch_id=<batch>/`, replacing whatever was there (v2 §7 partition-replace); remove
  the staging directory.
- *Done when:* a re-run of the same batch with no source changes produces
  byte-identical `batch_id=<batch>/part-00000.parquet` files for all five datasets
  (verifies idempotency at the storage step — `AGENTS.md` hard rule 7); an interrupted
  run (kill the process mid-write, as a manual test) leaves the previous
  `batch_id=<batch>/` partition intact and untouched, because nothing was swapped in.
- *Depends on:* BR-3, BR-4, BR-5.

**BR-7 — Reconciliation check + run summary**
- *Reads:* row counts from BR-3/BR-4/BR-5's in-memory results, post-write. *Writes:*
  the stdout summary (4.2.2); exit code.
- *Steps:* assert, per dataset, `rows_read == rows_loaded + rows_quarantined`; on
  failure, exit `2` **and do not swap the staged files into place** (fold this
  assertion into BR-6's swap step as a precondition); on success, print the summary
  line per dataset and exit `0`.
- *Done when:* a deliberately broken build (e.g. a row silently dropped instead of
  quarantined, introduced only as a test) trips exit `2`; the correct implementation
  exits `0` with counts that sum correctly for both real batches.
- *Depends on:* BR-6.

**BR-8 — Skip-if-unchanged (`--force`)**
- *Reads:* `bronze.file_manifest`'s last recorded SHA-256 per file for this
  `batch_id`. *Writes:* nothing, on skip; full run otherwise.
- *Steps:* before BR-2 onward, compute this run's file checksums and compare to the
  last successful run's `bronze.file_manifest` rows for the same `batch_id`; if all
  match and `--force` was not passed, print `"batch_2026_01: unchanged, skipping"` and
  exit `0` without touching `warehouse/bronze/`.
- *Done when:* running `data-loader batch_2026_01` twice in a row does no writes on
  the second run (verified by file mtimes on `warehouse/bronze/**/batch_id=batch_2026_01/`
  being unchanged); `--force` bypasses the skip and re-runs fully.
- *Depends on:* BR-6, BR-7 (needs a completed prior run to compare against).

#### 4.2.5 Non-goals for `data_loader` (bronze), stated explicitly

Bronze structures what arrived; it does not judge it (v2 §3.1). Out of scope for this
CLI, deliberately, because they are silver's job (v2 §4):

- No cross-file `sample_id` join or referential validation — orphan-VCF /
  orphan-manifest-row detection (the `S-0008` case) happens in silver, against
  bronze's already-landed output, not inside `data_loader`.
- No type casting beyond the mandatory `.`/`""` → NULL (`tumor_purity` stays the raw
  string `"63%"` or `"0.32"`; `collection_date` stays the raw string in whatever
  format it arrived).
- No vocabulary normalisation (`"LUNG "` stays `"LUNG "`).
- No deduplication or conflict resolution of the `S-0011` manifest rows — both land.

### 4.3 Testing plan for bronze

| ID | Test | Proves |
|---|---|---|
| **TB-1** | `CSQ` header-order test (BR-2's Done-when, formalised) | Schema drift is handled by parsing the header, not a hardcoded field list — the exercise's central trap |
| **TB-2** | Flag-only INFO field (`HOTSPOT`) round-trips to `'true'` without a `split('=')` crash | The naive-parser failure mode named in v1 §3.3 V1 does not occur |
| **TB-3** | Integration: `data-loader batch_2026_01` end-to-end, assert `bronze.file_manifest` row counts match an independent `wc -l`-style count per file | The loader's own accounting is trustworthy, checked against ground truth, not just internally consistent |
| **TB-4** | Integration: `data-loader batch_2026_02`, assert `S-0020` gets `is_truncated=true` and quarantines exactly one line, not zero and not the whole file | v1's central malformed-file trap is handled per the v2 §3.7 refined verdict |
| **TB-5** | Idempotency: run twice, diff `warehouse/bronze/**/batch_id=.../part-00000.parquet` byte-for-byte | `AGENTS.md` hard rule 7 — reproducibility |
| **TB-6** | Reconciliation invariant asserted as a real test, not just eyeballed in the summary | `rows_read = rows_loaded + rows_quarantined` holds for every dataset, both batches |

### 4.4 Silver layer — readiness checklist (not a task breakdown yet)

Before silver's own implementation plan gets written, bronze's output must satisfy the
following — re-derived from v2 §4, checked against what BR-1..BR-8 above actually
produce, not assumed:

- [ ] Every bronze row carries `batch_id, source_file, source_line_no, ingest_run_id,
      ingested_at_utc` — silver's `silver.quarantine` table (v2 §4.6) cites these as
      its own provenance columns; if bronze omits one, silver can't populate it without
      going back to bronze.
- [ ] `bronze.sample_manifest` retains **both** `S-0011` rows uncollapsed — silver's
      conflicting-duplicate detection (v2 §4.5) needs to see both to detect the
      conflict at all; BR-4 is specified to do this (4.2.4).
- [ ] `bronze.file_manifest.is_truncated` / `parse_status` is present per file — silver
      excludes `S-0020` on this flag (v2 §3.7) rather than re-deriving truncation
      itself; BR-5 is specified to write it.
- [ ] `bronze.vcf_headers` captures each file's declared `CSQ` order and INFO
      Type/Number — silver may need this for audit even though row-level `CSQ`
      splitting already happened in bronze; BR-2/BR-6 produce this.
- [ ] Cross-batch reads use `union_by_name=true` (v2 §3.3) so silver's ingest query
      doesn't need a per-batch branch when `CCF`/`GNOMAD_AF_POPMAX` appear — this is a
      property of how silver *reads* bronze, not something bronze needs to change to
      support.

**One requirement flagged, not resolved:** the vocabulary crosswalk files
(`config/crosswalks/tissue.yaml` etc., v2 §4.4) don't exist yet. Authoring them is a
one-time task blocking silver's normalisation step, and it should happen **after**
bronze ships — checking the crosswalk against bronze's actual landed distinct values
(not the v1 profiling numbers, which could drift if the loader's trim/NULL rules
surface something new) is cheap belt-and-suspenders and costs nothing to defer.

Silver's own **BR-style task breakdown is intentionally not written in this version** —
see §4.0.

### 4.5 Deferred entirely this pass

Gold layer: no plan drafted. v2 §5 remains the target design, picked up after silver
ships.
