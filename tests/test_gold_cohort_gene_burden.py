import duckdb

from gold_builder.contracts import load_contract
from gold_builder.marts import cohort_gene_burden

CONTRACT = load_contract("config/gold_contracts/gold_cohort_gene_burden_v1.yaml")


def test_tp53_numbers_against_real_data():
    con = duckdb.connect("warehouse/silver.duckdb")
    rows, quarantine = cohort_gene_burden.build(
        con, CONTRACT, run_id="test-run", run_timestamp="20260101T000000"
    )

    tp53 = next(r for r in rows if r["gene_symbol"] == "TP53")
    assert tp53["n_variants"] == 57
    assert tp53["n_distinct_samples"] == 19
    assert tp53["n_distinct_patients"] == 17
    assert tp53["n_samples_with_unknown_patient"] == 1

    # no column literally named "count"
    assert "count" not in tp53

    # real data has zero NULL-gene_symbol rows — this path stays unexercised here
    assert quarantine == []


def test_s0011_contributes_to_n_variants_but_not_n_distinct_patients():
    con = duckdb.connect("warehouse/silver.duckdb")

    with_s0011 = con.execute(
        "SELECT COUNT(*) FROM variant_calls WHERE gene_symbol='TP53'"
    ).fetchone()[0]
    without_s0011 = con.execute(
        "SELECT COUNT(*) FROM variant_calls WHERE gene_symbol='TP53' AND sample_id != 'S-0011'"
    ).fetchone()[0]

    assert with_s0011 == 57
    assert without_s0011 == 54
    assert with_s0011 - without_s0011 == 3  # S-0011's 3 TP53 variants, counted

    rows, _ = cohort_gene_burden.build(
        con, CONTRACT, run_id="test-run", run_timestamp="20260101T000000"
    )
    tp53 = next(r for r in rows if r["gene_symbol"] == "TP53")
    # S-0011's patient_id is NULL -> excluded from n_distinct_patients,
    # but it's exactly the "1" in n_samples_with_unknown_patient.
    assert tp53["n_samples_with_unknown_patient"] == 1


def test_gene_symbol_null_row_quarantines_synthetic():
    con = duckdb.connect()
    con.execute("CREATE TABLE samples (sample_id VARCHAR, patient_id VARCHAR)")
    con.execute("CREATE TABLE variant_calls (sample_id VARCHAR, chrom VARCHAR, pos VARCHAR, "
                 "ref VARCHAR, alt VARCHAR, gene_symbol VARCHAR, hotspot BOOLEAN, vaf DOUBLE)")
    con.execute("INSERT INTO samples VALUES ('S-1', 'P-1')")
    con.execute(
        "INSERT INTO variant_calls VALUES "
        "('S-1', 'chr1', '100', 'A', 'G', 'BRCA1', false, 0.3), "
        "('S-1', 'chr2', '200', 'C', 'T', NULL, false, 0.4)"
    )

    rows, quarantine = cohort_gene_burden.build(
        con, CONTRACT, run_id="test-run", run_timestamp="20260101T000000"
    )

    assert len(rows) == 1
    assert rows[0]["gene_symbol"] == "BRCA1"

    assert len(quarantine) == 1
    assert quarantine[0].exclusion_reason_code == "MISSING_GENE_SYMBOL"
    assert quarantine[0].missing_columns == ["gene_symbol"]
