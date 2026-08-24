from pathlib import Path

import duckdb

from silver_builder.crosswalks import load_crosswalk
from silver_builder.queries import (
    VARIANT_COUNT_PER_GENE_WITH_DISTINCT_PATIENTS,
    VARIANTS_IN_GENE_WITH_SAMPLE_TISSUE,
)
from silver_builder.run import run

CROSSWALKS = {
    "tissue": load_crosswalk("config/crosswalks/tissue.yaml"),
    "sequencing_platform": load_crosswalk("config/crosswalks/sequencing_platform.yaml"),
    "library_prep": load_crosswalk("config/crosswalks/library_prep.yaml"),
    "qc_status": load_crosswalk("config/crosswalks/qc_status.yaml"),
    "sex": load_crosswalk("config/crosswalks/sex.yaml"),
}


def _build_real_silver_db(tmp_path):
    summary = run(
        bronze_data_root="warehouse/bronze/data",
        explicit_data_files=None,
        out_root=str(tmp_path),
        run_id="test-run",
        run_timestamp="20260101T000000",
    )
    return summary.db_path


def test_join_query_returns_sane_nonempty_results(tmp_path):
    db_path = _build_real_silver_db(tmp_path)
    con = duckdb.connect(str(db_path))

    top_gene = con.execute(VARIANT_COUNT_PER_GENE_WITH_DISTINCT_PATIENTS).fetchone()[0]
    rows = con.execute(VARIANTS_IN_GENE_WITH_SAMPLE_TISSUE, [top_gene]).fetchall()

    assert len(rows) > 0
    for sample_id, gene_symbol, consequence, impact, tissue, diagnosis in rows:
        assert sample_id.startswith("S-")
        assert gene_symbol == top_gene
        # tissue is NULL only for S-0011 (its manifest rows conflicted at
        # bronze) — every other real sample has manifest data attached.
        assert tissue is not None or sample_id == "S-0011"


def test_aggregate_query_n_variants_and_n_distinct_patients_can_diverge(tmp_path):
    db_path = _build_real_silver_db(tmp_path)
    con = duckdb.connect(str(db_path))

    rows = con.execute(VARIANT_COUNT_PER_GENE_WITH_DISTINCT_PATIENTS).fetchall()
    assert len(rows) > 0

    # The exact trap this schema exists to prevent: a gene's variant count
    # must not be silently used as a patient count.
    diverging = [r for r in rows if r[1] != r[2]]
    assert diverging, "expected at least one gene where n_variants != n_distinct_patients"
