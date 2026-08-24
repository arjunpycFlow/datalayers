# Data Context: Genomic Data Foundation

## Data relationship: VCF files ↔ sample_manifest.csv

Each batch folder (`data/batch_2026_01/`, `data/batch_2026_02/`) contains two
kinds of raw input that are **independent sources describing the same cohort
from different angles**, joined at ingest time by `sample_id`:

- **VCF files** (`S-000N.somatic.vcf`) — one file per sample. This is the
  **molecular/fact data**: somatic variant calls (CHROM, POS, REF, ALT, QUAL,
  FILTER, INFO annotations, genotype/VAF). Grain = one row per variant call
  per sample. A VCF has no clinical context — it doesn't know what tissue,
  diagnosis, or patient the sample came from, only that a genotype column
  header carries the sample_id.

- **sample_manifest.csv** — one row per sample. This is the
  **clinical/technical dimension data**: patient linkage, tissue, diagnosis,
  disease group, tumor purity, reported/inferred sex, sequencing platform,
  QC status, collection date, free-text notes. It has no molecular data.

**Neither file is sufficient alone.** VCFs without the manifest are an
unlabeled pile of mutations — no way to group by cancer type, exclude
low-QC or low-purity samples, or reason about cohort-level questions.
The manifest without VCFs is clinical metadata with no biology attached.
Combining them is what turns raw pipeline output into data a researcher (or
an NL assistant) can actually query: "which samples have a variant in gene
X, and what tissue/diagnosis are they from" only becomes answerable once
variant rows and sample rows are joined.

**The join key is the contract.** `sample_id` must tie a VCF file
(filename + genotype column) to exactly one manifest row. Ingest must
validate this both ways: every VCF has a matching manifest row, every
manifest row has a matching VCF file. Breaks in that contract (duplicate
sample_id rows, orphaned files, missing files) are data-quality issues to
surface, not silently drop.

**Grain, in general terms** (specifics — column names, keys, exact tables —
belong to the parsing/modeling step, not here):

- Patient — highest level, one patient may have multiple samples.
- Sample — one manifest row, one VCF file. The natural join grain between
  the two sources.
- Variant call — one row within a sample's VCF. Many per sample.

Both sources arrive "as the pipeline dropped them" and are independently
messy (inconsistent formatting, mixed encodings, occasional bad rows/files).
Each needs its own validation and cleaning pass before being joined — the
manifest's messiness doesn't imply anything about a given VCF's cleanliness
and vice versa.

## Landing convention for `candidate_bundle/data/` (source, immutable)

This is the **general shape a new batch is expected to arrive in**, not a snapshot of
today's two folders — a pipeline built against the literal current tree will break the
day `batch_2026_03` lands. The pattern, inferred and confirmed against the two batches
present today:

```
candidate_bundle/data/
└── batch_<batch_id>/              one flat folder per landing event, e.g. batch_2026_01,
    │                               batch_2026_02, batch_2026_03, ... — no nesting deeper
    │                               than batch folder → files
    ├── sample_manifest.csv        exactly one per batch — the batch's clinical/technical
    │                               dimension table, one row expected per sample
    └── S-000N.somatic.vcf         one VCF per sample in that batch — the batch's
                                    molecular/fact data, filename carries sample_id
```

Every batch folder is expected to carry **both** artifact types together — a VCF set and
its manifest — because, per the relationship above, neither is independently useful:
ingest logic should be written against "a batch = manifest + VCFs, joined by
`sample_id`," not against a fixed file count or a fixed pair of batch names. Two
consequences that follow directly from that:

- **File count per batch is not fixed.** batch_2026_01 shipped 14 VCFs + 16 manifest
  rows (15 distinct sample_id), batch_2026_02 shipped 5 + 5. A new batch may ship any
  number of samples; ingest must discover files by listing the folder, never by assuming
  a count or a contiguous `S-000N` sequence.
- **1:1 between VCF files and manifest rows is the expectation, not a guarantee.**
  Because the two artifacts are independent sources that only agree to describe the same
  cohort *if the pipeline that produced them did its job*, every batch must be validated
  both directions on ingest (every VCF has a manifest row, every manifest row has a VCF)
  — never assumed from the fact that a manifest row exists or a file is present.

**Evidence this validation is load-bearing, not theoretical** — found by listing
`batch_2026_01` and diffing it against its manifest, not inferred from file names:

- **Orphaned manifest row:** `S-0008` / `P-0008` has a manifest row but no
  `S-0008.somatic.vcf` file on disk. A join keyed on `sample_id` alone will silently
  produce a sample with clinical metadata and zero variant rows unless this is checked
  for explicitly.
- **Duplicate `sample_id`:** `S-0011` appears as two manifest rows with the same
  `patient_id`/`collection_date` but different `tumor_purity` (57% vs 0.64 — likely the
  same value in two formats, but they disagree once parsed as floats: 0.57 vs 0.64).
  A join on `sample_id` will fan out the single `S-0011.somatic.vcf`'s variant rows
  against two manifest rows unless deduplicated first.

`batch_2026_02` has neither problem: VCF count and manifest row count both equal 5, 1:1.
That batch-to-batch difference is itself the point — do not generalize batch_2026_02's
cleanliness into an assumption future batches will hold to.

## Batches are not identical in shape

`batch_2026_02` adds new INFO fields (VCF) and at least one new manifest
column, plus one malformed file. New batches should extend the schema
additively — existing batch_2026_01 tables/queries must keep working
unchanged when a new batch lands.
