from dataclasses import dataclass
from datetime import date


@dataclass
class SilverSample:
    """One row of silver.samples — grain: one row per sample."""

    sample_id: str
    patient_id: str | None
    batch_id: str | None
    collection_date: date | None
    collection_date_raw: str | None
    tissue: str | None
    diagnosis: str | None
    disease_group: str | None
    tumor_purity: float | None
    sex_reported: str | None
    sex_inferred: str | None
    sex_concordant: bool | None
    sequencing_platform: str | None
    qc_status: str | None
    library_prep: str | None
    is_ffpe: bool
    is_repeat_library: bool
    notes: str | None
    has_variant_data: bool
    bronze_source_file: str | None
    bronze_run_id: str
    bronze_run_timestamp: str


@dataclass
class SilverVariantCall:
    """One row of silver.variant_calls — grain: one row per (sample, variant)."""

    sample_id: str
    chrom: str
    pos: str
    ref: str
    alt: str
    id: str | None
    qual: float | None
    filter: str | None
    caller: str | None
    max_pop_af: float | None
    hotspot: bool
    gene_symbol: str | None
    consequence: str | None
    impact: str | None
    hgvsc: str | None
    hgvsp: str | None
    exon: str | None
    mane_select: str | None
    ccf: float | None
    gnomad_af_popmax: float | None
    gt: str | None
    ad: str | None
    dp: int | None
    vaf: float | None
    pipeline_version: str | None
    bronze_source_file: str | None
    bronze_run_id: str
    bronze_run_timestamp: str


@dataclass
class SilverQuarantine:
    """One row of silver.quarantine — normalization-level failures only."""

    entity_type: str  # "sample"
    sample_id: str
    field_name: str
    raw_value: str
    reason_code: str  # UNMAPPED_VOCABULARY_TERM | PURITY_OUT_OF_RANGE
    reason_detail: str
    run_id: str
    run_timestamp: str
