import duckdb

from gold_builder.run import run


def _table_counts(db_path):
    con = duckdb.connect(str(db_path))
    tables = [
        r[0]
        for r in con.execute(
            "SELECT table_schema || '.' || table_name FROM information_schema.tables"
        ).fetchall()
    ]
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def test_rerun_against_unchanged_silver_produces_identical_content(tmp_path):
    summary_1 = run(
        silver_db="warehouse/silver.duckdb",
        out_root=str(tmp_path / "run1"),
        mart_filter=None,
        run_id="run-1",
        run_timestamp="20260101T000000",
    )
    summary_2 = run(
        silver_db="warehouse/silver.duckdb",
        out_root=str(tmp_path / "run2"),
        mart_filter=None,
        run_id="run-2",
        run_timestamp="20260102T000000",
    )

    counts_1 = _table_counts(summary_1.gold_db_path)
    counts_2 = _table_counts(summary_2.gold_db_path)
    assert counts_1 == counts_2
    assert len(counts_1) > 0
