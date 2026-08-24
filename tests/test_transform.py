from silver_builder.crosswalks import load_crosswalk
from silver_builder.transform import transform_rows

CROSSWALKS = {
    "tissue": load_crosswalk("config/crosswalks/tissue.yaml"),
    "sequencing_platform": load_crosswalk("config/crosswalks/sequencing_platform.yaml"),
    "library_prep": load_crosswalk("config/crosswalks/library_prep.yaml"),
    "qc_status": load_crosswalk("config/crosswalks/qc_status.yaml"),
    "sex": load_crosswalk("config/crosswalks/sex.yaml"),
}


def _bronze_row(**overrides):
    row = {
        "sample_id": "S-9001",
        "patient_id": "P-9001",
        "batch_id": "batch_test",
        "collection_date": "2026-01-05",
        "tissue": "Lung",
        "diagnosis": "Lung adenocarcinoma",
        "disease_group": "Thoracic",
        "tumor_purity": "0.32",
        "sex_reported": "F",
        "sex_inferred": "F",
        "sequencing_platform": "NovaSeq X",
        "qc_status": "PASS",
        "notes": None,
        "library_prep": None,
        "chrom": "chr1",
        "pos": "12345",
        "id": None,
        "ref": "A",
        "alt": "G",
        "qual": "500",
        "filter": "PASS",
        "info": {},
        "format_keys": ["GT", "AD", "DP", "VAF"],
        "genotype_values": ["0/1", "78,40", "118", "0.3390"],
        "vcf_source_file": "S-9001.somatic.vcf",
        "manifest_source_file": "sample_manifest.csv",
        "pipeline_version": "SyntheticPipeline_v1.4",
        "run_id": "test-run",
        "run_timestamp": "20260101T000000",
    }
    row.update(overrides)
    return row


def test_out_of_range_purity_quarantines_sample_but_variant_still_lands():
    rows = [_bronze_row(tumor_purity="630%")]

    samples, variant_calls, quarantine = transform_rows(
        rows, CROSSWALKS, run_id="test-run", run_timestamp="20260101T000000"
    )

    assert samples == []
    assert len(variant_calls) == 1
    assert variant_calls[0].sample_id == "S-9001"

    purity_failures = [q for q in quarantine if q.reason_code == "PURITY_OUT_OF_RANGE"]
    assert len(purity_failures) == 1
    assert purity_failures[0].sample_id == "S-9001"


def test_valid_row_produces_one_sample_and_one_variant_call():
    rows = [_bronze_row()]
    samples, variant_calls, quarantine = transform_rows(
        rows, CROSSWALKS, run_id="test-run", run_timestamp="20260101T000000"
    )
    assert len(samples) == 1
    assert len(variant_calls) == 1
    assert quarantine == []
    assert samples[0].tissue == "Lung"


def test_multiple_variant_rows_same_sample_produce_one_sample_record():
    rows = [
        _bronze_row(chrom="chr1", pos="100"),
        _bronze_row(chrom="chr2", pos="200"),
    ]
    samples, variant_calls, _ = transform_rows(
        rows, CROSSWALKS, run_id="test-run", run_timestamp="20260101T000000"
    )
    assert len(samples) == 1
    assert len(variant_calls) == 2


def test_genotype_extracted_end_to_end_and_mane_select_additive():
    batch1_row = _bronze_row(info={"CSQ_SYMBOL": "ARID1A"})  # no MANE_SELECT — batch 1
    batch2_row = _bronze_row(
        sample_id="S-9002",
        info={"CSQ_SYMBOL": "ARID1A", "CSQ_MANE_SELECT": "NM_006015.6"},
    )
    _, variant_calls, _ = transform_rows(
        [batch1_row, batch2_row], CROSSWALKS, run_id="test-run", run_timestamp="20260101T000000"
    )
    b1, b2 = variant_calls
    assert b1.gt == "0/1"
    assert b1.dp == 118
    assert b1.vaf == 0.3390
    assert b1.mane_select is None
    assert b2.mane_select == "NM_006015.6"


def test_manifest_only_row_has_variant_data_false():
    rows = [_bronze_row(chrom=None, pos=None, ref=None, alt=None, qual=None, filter=None)]
    samples, variant_calls, _ = transform_rows(
        rows, CROSSWALKS, run_id="test-run", run_timestamp="20260101T000000"
    )
    assert len(samples) == 1
    assert samples[0].has_variant_data is False
    assert variant_calls == []
