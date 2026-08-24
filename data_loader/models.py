from dataclasses import dataclass, field


@dataclass
class DataRow:
    """One row of bronze.data: one (sample, variant) pair, or one manifest-only
    row (all variant columns NULL) for a sample with no matching VCF."""

    sample_id: str | None
    patient_id: str | None
    batch_id: str | None
    collection_date: str | None
    tissue: str | None
    diagnosis: str | None
    disease_group: str | None
    tumor_purity: str | None
    sex_reported: str | None
    sex_inferred: str | None
    sequencing_platform: str | None
    qc_status: str | None
    notes: str | None
    library_prep: str | None
    chrom: str | None
    pos: str | None
    id: str | None
    ref: str | None
    alt: str | None
    qual: str | None
    filter: str | None
    info: dict[str, str] = field(default_factory=dict)
    format_keys: list[str] = field(default_factory=list)
    genotype_values: list[str] = field(default_factory=list)
    vcf_source_file: str | None = None
    manifest_source_file: str | None = None
    pipeline_version: str | None = None
    run_id: str = ""
    run_timestamp: str = ""


@dataclass
class QuarantineRow:
    """One row of bronze.quarantine: a record that couldn't be parsed or
    safely combined, kept whole with its raw text."""

    batch_id: str
    entity_type: str  # vcf_row | manifest_row | manifest_conflicting_duplicate
    source_file: str
    source_line_no: str
    raw_text: str
    reason_code: str
    reason_detail: str
    run_id: str
    run_timestamp: str
