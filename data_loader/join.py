from data_loader.manifest import ParsedManifestRow
from data_loader.models import DataRow
from data_loader.vcf_rows import ParsedVcfRow

_MANIFEST_FIELDS = (
    "patient_id",
    "batch_id",
    "collection_date",
    "tissue",
    "diagnosis",
    "disease_group",
    "tumor_purity",
    "sex_reported",
    "sex_inferred",
    "sequencing_platform",
    "qc_status",
    "notes",
    "library_prep",
)


def _manifest_fields(manifest_row: ParsedManifestRow | None) -> dict:
    if manifest_row is None:
        return {name: None for name in _MANIFEST_FIELDS}
    return {name: getattr(manifest_row, name) for name in _MANIFEST_FIELDS}


def join_records(
    vcf_rows: list[ParsedVcfRow],
    manifest_rows: list[ParsedManifestRow],
    run_id: str = "",
    run_timestamp: str = "",
) -> list[DataRow]:
    """One DataRow per (sample, variant); a sample present on only one side
    still lands with the other side's columns NULL — never dropped."""

    manifest_by_sample = {r.sample_id: r for r in manifest_rows}
    vcf_by_sample: dict[str, list[ParsedVcfRow]] = {}
    for row in vcf_rows:
        vcf_by_sample.setdefault(row.sample_id, []).append(row)

    all_sample_ids = set(manifest_by_sample) | set(vcf_by_sample)
    data_rows: list[DataRow] = []

    for sample_id in sorted(all_sample_ids):
        manifest_row = manifest_by_sample.get(sample_id)
        sample_vcf_rows = vcf_by_sample.get(sample_id, [])
        manifest_fields = _manifest_fields(manifest_row)
        manifest_source_file = manifest_row.source_file if manifest_row else None

        if sample_vcf_rows:
            for vcf_row in sample_vcf_rows:
                data_rows.append(
                    DataRow(
                        sample_id=sample_id,
                        **manifest_fields,
                        chrom=vcf_row.chrom,
                        pos=vcf_row.pos,
                        id=vcf_row.id,
                        ref=vcf_row.ref,
                        alt=vcf_row.alt,
                        qual=vcf_row.qual,
                        filter=vcf_row.filter,
                        info=vcf_row.info,
                        format_keys=vcf_row.format_keys,
                        genotype_values=vcf_row.genotype_values,
                        vcf_source_file=vcf_row.source_file,
                        manifest_source_file=manifest_source_file,
                        pipeline_version=vcf_row.pipeline_version,
                        run_id=run_id,
                        run_timestamp=run_timestamp,
                    )
                )
        else:
            # Manifest row with no matching VCF on disk (e.g. S-0008) — still
            # lands, variant columns NULL. A real fact, not an error to hide.
            data_rows.append(
                DataRow(
                    sample_id=sample_id,
                    **manifest_fields,
                    chrom=None,
                    pos=None,
                    id=None,
                    ref=None,
                    alt=None,
                    qual=None,
                    filter=None,
                    info={},
                    format_keys=[],
                    genotype_values=[],
                    vcf_source_file=None,
                    manifest_source_file=manifest_source_file,
                    pipeline_version=None,
                    run_id=run_id,
                    run_timestamp=run_timestamp,
                )
            )

    return data_rows
