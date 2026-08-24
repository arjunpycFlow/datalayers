import duckdb

from gold_builder.contracts import load_contract
from gold_builder.marts import sample_clinical_profile
from gold_builder.writer import write_mart

CONTRACT = load_contract("config/gold_contracts/gold_sample_clinical_profile_v1.yaml")


def test_restricted_mart_carries_exact_fidelity_dates_and_purity():
    silver_con = duckdb.connect("warehouse/silver.duckdb")
    rows, quarantine = sample_clinical_profile.build(
        silver_con, CONTRACT, run_id="test-run", run_timestamp="20260101T000000"
    )

    silver_values = {
        r[0]: (r[1], r[2])
        for r in silver_con.execute(
            "SELECT sample_id, collection_date, tumor_purity FROM samples"
        ).fetchall()
    }

    assert rows  # some samples pass (S-0011 won't, its patient_id is NULL)
    for row in rows:
        exact_date, exact_purity = silver_values[row["sample_id"]]
        assert row["collection_date"] == exact_date  # unbanded, ungeneralised
        assert row["tumor_purity"] == exact_purity  # exact, not banded low/medium/high


def test_write_mart_creates_schema_and_both_tables():
    gold_con = duckdb.connect()
    silver_con = duckdb.connect("warehouse/silver.duckdb")
    rows, quarantine = sample_clinical_profile.build(
        silver_con, CONTRACT, run_id="test-run", run_timestamp="20260101T000000"
    )

    write_mart(gold_con, CONTRACT, rows, quarantine)

    schemas = {r[0] for r in gold_con.execute(
        "SELECT schema_name FROM information_schema.schemata"
    ).fetchall()}
    assert "gold_restricted" in schemas

    row_count = gold_con.execute(
        "SELECT COUNT(*) FROM gold_restricted.gold_sample_clinical_profile_v1"
    ).fetchone()[0]
    assert row_count == len(rows)

    q_count = gold_con.execute(
        "SELECT COUNT(*) FROM gold_restricted.gold_sample_clinical_profile_quarantine_v1"
    ).fetchone()[0]
    assert q_count == len(quarantine)
    assert len(rows) + len(quarantine) > 0
