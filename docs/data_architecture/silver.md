# Silver layer — `silver_builder`

Reads bronze's `data` Parquet output, normalizes types and vocabulary, and writes a
trust-layer schema (patients/samples/variant_calls/batches, plus a
normalization-failure quarantine) to `warehouse/silver.duckdb`:

```bash
uv run silver-builder
```

By default it auto-discovers each batch's latest `data_*.parquet` under
`warehouse/bronze/data/`. To rebuild from a specific bronze run instead:

```bash
uv run silver-builder --data-files warehouse/bronze/data/batch_2026_01/data_<timestamp>.parquet [...]
```

**What it does that bronze didn't:**
- Normalizes `tumor_purity` and all VCF-native allele-frequency-like fields
  (`VAF`, `MAX_POP_AF`, `GNOMAD_AF_POPMAX`, `CCF`) to `[0,1]` fractions.
- Maps `tissue`/`sequencing_platform`/`library_prep`/`qc_status` to controlled
  vocabularies via `config/crosswalks/*.yaml` — an unmapped value quarantines,
  never guessed at (see [Next phase: unmapped-vocabulary review](../operations.md#next-phase-unmapped-vocabulary-review)).
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

**Reads / writes / exit codes:**

| | `silver-builder` |
|---|---|
| Reads | `warehouse/bronze/data/` |
| Writes | `warehouse/silver.duckdb` |
| Exit `0` | success |
| Exit `1` | no bronze data files found |
| Exit `2` | reconciliation invariant failed |
| Idempotency | full rebuild (`CREATE OR REPLACE`) every run |

## Internal flow

```mermaid
flowchart TD
    Bronze["bronze.data
    (auto-discovered latest
    per batch, or --data-files)"] --> Norm["Normalize:
    tumor_purity, VAF/MAX_POP_AF/
    GNOMAD_AF_POPMAX/CCF → [0,1]"]
    Norm --> Crosswalk["Map controlled vocab
    (tissue, platform, prep, qc_status)
    via config/crosswalks/*.yaml"]
    Crosswalk --> Split{"Splittable into
    grain-correct rows?"}
    Split -->|"yes"| Tables["silver.patients
    silver.samples
    silver.variant_calls
    silver.batches"]
    Split -->|"no — unmapped
    vocabulary term"| SQ["silver.quarantine
    reason_code = UNMAPPED_VOCABULARY_TERM"]
    Tables --> Recon["Reconciliation: every distinct
    sample_id lands in exactly one of
    silver.samples or silver.quarantine"]
    SQ --> Recon
```

Grain-splitting happens *after* normalization, not before — a value has to be
on a known scale and in a known vocabulary before it's meaningful to assign it
to `patients` vs. `samples` vs. `variant_calls`. This is also why silver fully
rebuilds every run rather than incrementally patching: a crosswalk update
(new canonical term added) should reclassify every historical row that term
touches, not just new ones.

---

[← Back to README](../../README.md)
