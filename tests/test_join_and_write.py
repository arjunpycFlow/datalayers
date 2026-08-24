from pathlib import Path

import duckdb

from data_loader.join import join_records
from data_loader.manifest import parse_manifest
from data_loader.vcf_headers import parse_vcf_headers
from data_loader.vcf_rows import parse_vcf_rows
from data_loader.writer import write_bronze

DATA_ROOT = Path("candidate_bundle/data")


def _load_batch(batch_id: str):
    batch_dir = DATA_ROOT / batch_id
    manifest_rows, manifest_quarantine, _ = parse_manifest(
        batch_dir / "sample_manifest.csv", batch_id=batch_id
    )

    vcf_rows = []
    vcf_quarantine = []
    for vcf_path in sorted(batch_dir.glob("*.somatic.vcf")):
        contract = parse_vcf_headers(vcf_path)
        rows, quarantined, _ = parse_vcf_rows(vcf_path, contract, batch_id=batch_id)
        vcf_rows.extend(rows)
        vcf_quarantine.extend(quarantined)

    data_rows = join_records(vcf_rows, manifest_rows)
    quarantine_rows = manifest_quarantine + vcf_quarantine
    return data_rows, quarantine_rows


def test_s0008_lands_as_variant_null_row():
    data_rows, _ = _load_batch("batch_2026_01")

    s0008_rows = [r for r in data_rows if r.sample_id == "S-0008"]
    assert len(s0008_rows) == 1
    assert s0008_rows[0].chrom is None
    assert s0008_rows[0].tissue is not None  # manifest side is populated


def test_s0011_variants_land_with_null_manifest_fields_manifest_rows_quarantined():
    data_rows, quarantine_rows = _load_batch("batch_2026_01")

    s0011_rows = [r for r in data_rows if r.sample_id == "S-0011"]
    assert len(s0011_rows) > 0  # its VCF variant calls are valid, so they land
    assert all(r.tissue is None for r in s0011_rows)  # manifest side unresolved

    conflicts = [
        q
        for q in quarantine_rows
        if q.reason_code == "CONFLICTING_DUPLICATE" and "S-0011" in q.raw_text
    ]
    assert len(conflicts) == 2  # both manifest rows quarantined


def test_rerun_produces_distinct_timestamped_files_first_run_untouched(tmp_path):
    data_rows, quarantine_rows = _load_batch("batch_2026_01")

    data_path_1, quarantine_path_1 = write_bronze(
        data_rows, quarantine_rows, str(tmp_path), "batch_2026_01", "20260101T000000"
    )
    contents_1 = data_path_1.read_bytes()

    data_path_2, quarantine_path_2 = write_bronze(
        data_rows, quarantine_rows, str(tmp_path), "batch_2026_01", "20260101T000001"
    )

    assert data_path_1 != data_path_2
    assert quarantine_path_1 != quarantine_path_2
    assert data_path_1.exists()
    assert data_path_1.read_bytes() == contents_1  # untouched by the second run


def test_written_parquet_is_readable_and_row_count_matches(tmp_path):
    data_rows, quarantine_rows = _load_batch("batch_2026_01")
    data_path, quarantine_path = write_bronze(
        data_rows, quarantine_rows, str(tmp_path), "batch_2026_01", "20260101T000000"
    )

    con = duckdb.connect()
    count = con.sql(f"SELECT COUNT(*) FROM read_parquet('{data_path}')").fetchone()[0]
    assert count == len(data_rows)

    q_count = con.sql(
        f"SELECT COUNT(*) FROM read_parquet('{quarantine_path}')"
    ).fetchone()[0]
    assert q_count == len(quarantine_rows)
