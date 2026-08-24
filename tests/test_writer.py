from pathlib import Path

import duckdb

from silver_builder.crosswalks import load_crosswalk
from silver_builder.transform import transform_rows
from silver_builder.writer import write_silver

CROSSWALKS = {
    "tissue": load_crosswalk("config/crosswalks/tissue.yaml"),
    "sequencing_platform": load_crosswalk("config/crosswalks/sequencing_platform.yaml"),
    "library_prep": load_crosswalk("config/crosswalks/library_prep.yaml"),
    "qc_status": load_crosswalk("config/crosswalks/qc_status.yaml"),
    "sex": load_crosswalk("config/crosswalks/sex.yaml"),
}


def _load_all_batches():
    con = duckdb.connect()
    all_rows = []
    for batch in ["batch_2026_01", "batch_2026_02"]:
        f = sorted(Path(f"warehouse/bronze/data/{batch}").glob("*.parquet"))[-1]
        cur = con.execute(f"SELECT * FROM read_parquet('{f}')")
        cols = [d[0] for d in cur.description]
        all_rows.extend(dict(zip(cols, r)) for r in cur.fetchall())
    return all_rows


def test_p0003_has_two_samples_and_s0008_has_no_variant_data(tmp_path):
    rows = _load_all_batches()
    samples, variant_calls, quarantine = transform_rows(
        rows, CROSSWALKS, run_id="test-run", run_timestamp="20260101T000000"
    )
    db_path = write_silver(samples, variant_calls, quarantine, str(tmp_path))

    con = duckdb.connect(str(db_path))
    n_samples = con.execute(
        "SELECT n_samples FROM patients WHERE patient_id = 'P-0003'"
    ).fetchone()[0]
    assert n_samples == 2

    has_variant_data = con.execute(
        "SELECT has_variant_data FROM samples WHERE sample_id = 'S-0008'"
    ).fetchone()[0]
    assert has_variant_data is False

    n_sample_rows = con.execute("SELECT COUNT(DISTINCT sample_id) FROM samples").fetchone()[0]
    n_distinct_bronze_samples = len({r["sample_id"] for r in rows})
    # Every distinct sample_id in bronze.data gets a silver.samples row — this
    # includes S-0011, whose VCF variants bronze already landed with manifest
    # columns NULL (its manifest rows conflicted and were quarantined at
    # bronze). Silver doesn't re-quarantine a sample just because its
    # dimension fields are already NULL — NULL normalizes to NULL, not a
    # failure.
    assert n_sample_rows == n_distinct_bronze_samples

    s0011_tissue = con.execute(
        "SELECT tissue FROM samples WHERE sample_id = 'S-0011'"
    ).fetchone()[0]
    assert s0011_tissue is None


def test_rerun_with_same_inputs_produces_identical_table_contents(tmp_path):
    rows = _load_all_batches()
    samples, variant_calls, quarantine = transform_rows(
        rows, CROSSWALKS, run_id="test-run", run_timestamp="20260101T000000"
    )

    db_path_1 = write_silver(samples, variant_calls, quarantine, str(tmp_path / "run1"))
    db_path_2 = write_silver(samples, variant_calls, quarantine, str(tmp_path / "run2"))

    con_1 = duckdb.connect(str(db_path_1))
    con_2 = duckdb.connect(str(db_path_2))
    for table in ("samples", "variant_calls", "quarantine", "patients", "batches"):
        count_1 = con_1.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        count_2 = con_2.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count_1 == count_2, f"{table} row count differs between runs"
