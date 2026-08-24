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

## Batches are not identical in shape

`batch_2026_02` adds new INFO fields (VCF) and at least one new manifest
column, plus one malformed file. New batches should extend the schema
additively — existing batch_2026_01 tables/queries must keep working
unchanged when a new batch lands.
