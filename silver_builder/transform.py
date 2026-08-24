from silver_builder.crosswalks import apply_crosswalk
from silver_builder.errors import NormalizationError
from silver_builder.genotype import extract_genotype
from silver_builder.models import SilverQuarantine, SilverSample, SilverVariantCall
from silver_builder.normalize import (
    derive_notes_flags,
    normalize_af,
    normalize_date,
    normalize_purity,
)


def _normalize_field(
    field_name: str,
    raw: str | None,
    crosswalk: dict[str, str],
    sample_id: str,
    quarantine: list[SilverQuarantine],
    run_id: str,
    run_timestamp: str,
) -> str | None:
    try:
        return apply_crosswalk(raw, crosswalk, field_name)
    except NormalizationError as e:
        quarantine.append(
            SilverQuarantine(
                entity_type="sample",
                sample_id=sample_id,
                field_name=field_name,
                raw_value=str(raw),
                reason_code=e.reason_code,
                reason_detail=e.detail,
                run_id=run_id,
                run_timestamp=run_timestamp,
            )
        )
        return None


def _build_sample(
    row: dict, crosswalks: dict[str, dict[str, str]], run_id: str, run_timestamp: str
) -> tuple[SilverSample | None, list[SilverQuarantine]]:
    sample_id = row["sample_id"]
    quarantine: list[SilverQuarantine] = []

    tissue = _normalize_field(
        "tissue", row.get("tissue"), crosswalks["tissue"], sample_id, quarantine,
        run_id, run_timestamp,
    )
    platform = _normalize_field(
        "sequencing_platform", row.get("sequencing_platform"),
        crosswalks["sequencing_platform"], sample_id, quarantine, run_id, run_timestamp,
    )
    library_prep = None
    if row.get("library_prep"):
        library_prep = _normalize_field(
            "library_prep", row.get("library_prep"), crosswalks["library_prep"],
            sample_id, quarantine, run_id, run_timestamp,
        )
    qc_status = _normalize_field(
        "qc_status", row.get("qc_status"), crosswalks["qc_status"], sample_id,
        quarantine, run_id, run_timestamp,
    )
    sex_reported = _normalize_field(
        "sex_reported", row.get("sex_reported"), crosswalks["sex"], sample_id,
        quarantine, run_id, run_timestamp,
    )
    sex_inferred = _normalize_field(
        "sex_inferred", row.get("sex_inferred"), crosswalks["sex"], sample_id,
        quarantine, run_id, run_timestamp,
    )

    try:
        tumor_purity = normalize_purity(row.get("tumor_purity"))
    except NormalizationError as e:
        quarantine.append(
            SilverQuarantine(
                entity_type="sample",
                sample_id=sample_id,
                field_name="tumor_purity",
                raw_value=str(row.get("tumor_purity")),
                reason_code=e.reason_code,
                reason_detail=e.detail,
                run_id=run_id,
                run_timestamp=run_timestamp,
            )
        )
        tumor_purity = None

    if quarantine:
        return None, quarantine

    collection_date = normalize_date(row.get("collection_date"))
    is_ffpe, is_repeat_library = derive_notes_flags(row.get("notes"))

    sex_concordant = None
    if sex_reported is not None and sex_inferred is not None:
        sex_concordant = sex_reported == sex_inferred

    sample = SilverSample(
        sample_id=sample_id,
        patient_id=row.get("patient_id"),
        batch_id=row.get("batch_id"),
        collection_date=collection_date,
        collection_date_raw=row.get("collection_date"),
        tissue=tissue,
        diagnosis=row.get("diagnosis"),
        disease_group=row.get("disease_group"),
        tumor_purity=tumor_purity,
        sex_reported=sex_reported,
        sex_inferred=sex_inferred,
        sex_concordant=sex_concordant,
        sequencing_platform=platform,
        qc_status=qc_status,
        library_prep=library_prep,
        is_ffpe=is_ffpe,
        is_repeat_library=is_repeat_library,
        notes=row.get("notes"),
        has_variant_data=row.get("chrom") is not None,
        bronze_source_file=row.get("manifest_source_file"),
        bronze_run_id=run_id,
        bronze_run_timestamp=run_timestamp,
    )
    return sample, quarantine


def _build_variant_call(row: dict, run_id: str, run_timestamp: str) -> SilverVariantCall:
    info = row.get("info") or {}
    gt, ad, dp, vaf = extract_genotype(
        row.get("format_keys") or [], row.get("genotype_values") or []
    )
    return SilverVariantCall(
        sample_id=row["sample_id"],
        chrom=row["chrom"],
        pos=row["pos"],
        ref=row["ref"],
        alt=row["alt"],
        id=row.get("id"),
        qual=float(row["qual"]) if row.get("qual") is not None else None,
        filter=row.get("filter"),
        caller=info.get("CALLER"),
        # Allele-frequency-like INFO fields are bounded [0,1]; normalize_af is a
        # no-op for values already in range (true for these fields in both real
        # batches) and corrects the ones that aren't (true for VAF in batch 2).
        max_pop_af=normalize_af(info.get("MAX_POP_AF")),
        hotspot=info.get("HOTSPOT") == "true",
        gene_symbol=info.get("CSQ_SYMBOL"),
        consequence=info.get("CSQ_Consequence"),
        impact=info.get("CSQ_IMPACT"),
        hgvsc=info.get("CSQ_HGVSc"),
        hgvsp=info.get("CSQ_HGVSp"),
        exon=info.get("CSQ_EXON"),
        mane_select=info.get("CSQ_MANE_SELECT"),
        ccf=normalize_af(info.get("CCF")),
        gnomad_af_popmax=normalize_af(info.get("GNOMAD_AF_POPMAX")),
        gt=gt,
        ad=ad,
        dp=dp,
        vaf=vaf,
        pipeline_version=row.get("pipeline_version"),
        bronze_source_file=row.get("vcf_source_file"),
        bronze_run_id=run_id,
        bronze_run_timestamp=run_timestamp,
    )


def transform_rows(
    rows: list[dict],
    crosswalks: dict[str, dict[str, str]],
    run_id: str,
    run_timestamp: str,
) -> tuple[list[SilverSample], list[SilverVariantCall], list[SilverQuarantine]]:
    samples: list[SilverSample] = []
    variant_calls: list[SilverVariantCall] = []
    quarantine: list[SilverQuarantine] = []
    seen_sample_ids: set[str] = set()

    for row in rows:
        sample_id = row["sample_id"]
        if sample_id not in seen_sample_ids:
            seen_sample_ids.add(sample_id)
            sample, sample_quarantine = _build_sample(row, crosswalks, run_id, run_timestamp)
            if sample is not None:
                samples.append(sample)
            quarantine.extend(sample_quarantine)

        if row.get("chrom") is not None:
            variant_calls.append(_build_variant_call(row, run_id, run_timestamp))

    return samples, variant_calls, quarantine
