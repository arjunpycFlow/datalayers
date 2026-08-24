import pytest

from gold_builder.run import (
    ReconciliationError,
    SchemaLeakError,
    _check_not_relevant_absent,
    _check_reconciliation,
    run,
)
from gold_builder.contracts import load_contract
from gold_builder.writer import connect, write_mart


def test_row_level_reconciliation_trips_on_broken_build():
    with pytest.raises(ReconciliationError):
        _check_reconciliation(
            "some_mart", "row_level", n_source_rows=10, rows=[{}] * 8, quarantine=[]
        )  # 8 accounted, 10 expected — 2 silently dropped


def test_row_level_reconciliation_passes_when_accounted_for():
    _check_reconciliation(
        "some_mart", "row_level", n_source_rows=10, rows=[{}] * 8, quarantine=[object()] * 2
    )  # no raise


def test_aggregate_reconciliation_uses_sum_of_n_variants():
    with pytest.raises(ReconciliationError):
        _check_reconciliation(
            "agg_mart", "aggregate", n_source_rows=100,
            rows=[{"n_variants": 50}, {"n_variants": 40}], quarantine=[],
        )  # 90 accounted, 100 expected


def test_not_relevant_column_leak_is_caught(tmp_path):
    contract = load_contract("config/gold_contracts/gold_variant_gene_lookup_v1.yaml")
    gold_con = connect(str(tmp_path))
    write_mart(gold_con, contract, rows=[], quarantine=[])
    _check_not_relevant_absent(gold_con, contract)  # no raise — real writer respects the contract

    # Now simulate a leak: add a not_relevant column to the actual table.
    gold_con.execute(
        f"ALTER TABLE {contract.schema}.{contract.mart} ADD COLUMN collection_date VARCHAR"
    )
    with pytest.raises(SchemaLeakError):
        _check_not_relevant_absent(gold_con, contract)


def test_full_run_against_real_silver_output(tmp_path):
    summary = run(
        silver_db="warehouse/silver.duckdb",
        out_root=str(tmp_path),
        mart_filter=None,
        run_id="test-run",
        run_timestamp="20260101T000000",
    )

    assert len(summary.marts) == 3
    by_name = {m.mart: m for m in summary.marts}

    assert by_name["gold_variant_gene_lookup_v1"].n_quarantined > 0  # S-0011's rows
    assert by_name["gold_cohort_gene_burden_v1"].n_quarantined == 0  # no NULL gene_symbol
    assert by_name["gold_sample_clinical_profile_v1"].n_rows > 0

    assert summary.gold_db_path.exists()
