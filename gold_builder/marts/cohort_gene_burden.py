import duckdb

from gold_builder.apply import GoldQuarantineRecord
from gold_builder.models import GoldContract

AGGREGATE_QUERY = """
    SELECT
        v.gene_symbol,
        COUNT(*) AS n_variants,
        COUNT(DISTINCT v.sample_id) AS n_distinct_samples,
        COUNT(DISTINCT s.patient_id) AS n_distinct_patients,
        COUNT(DISTINCT CASE WHEN s.patient_id IS NULL THEN v.sample_id END)
            AS n_samples_with_unknown_patient,
        COUNT(*) FILTER (WHERE v.hotspot) AS n_hotspot_variants,
        AVG(v.vaf) AS mean_vaf
    FROM variant_calls v
    JOIN samples s USING (sample_id)
    WHERE v.gene_symbol IS NOT NULL
    GROUP BY v.gene_symbol
    ORDER BY n_variants DESC
"""

# gene_symbol IS NULL rows can't contribute to any gene's aggregate — they're
# the contributing-row quarantine for this mart. Confirmed 0/1089 real rows
# hit this; kept as a real, if currently unexercised, guard.
QUARANTINE_QUERY = """
    SELECT sample_id, chrom, pos, ref, alt
    FROM variant_calls
    WHERE gene_symbol IS NULL
"""


def build(
    con: duckdb.DuckDBPyConnection,
    contract: GoldContract,
    run_id: str,
    run_timestamp: str,
) -> tuple[list[dict], list[GoldQuarantineRecord]]:
    cur = con.execute(AGGREGATE_QUERY)
    cols = [d[0] for d in cur.description]
    rows_out = [
        {col: value for col, value in zip(cols, record) if col in contract.present_columns}
        for record in cur.fetchall()
    ]

    quarantine_out: list[GoldQuarantineRecord] = []
    for sample_id, chrom, pos, ref, alt in con.execute(QUARANTINE_QUERY).fetchall():
        row_id = f"sample_id={sample_id},chrom={chrom},pos={pos},ref={ref},alt={alt}"
        quarantine_out.append(
            GoldQuarantineRecord(
                mart=contract.mart,
                exclusion_reason_code="MISSING_GENE_SYMBOL",
                exclusion_detail="gene_symbol is NULL; cannot contribute to any gene's aggregate",
                missing_columns=["gene_symbol"],
                row_identifier=row_id,
                run_id=run_id,
                run_timestamp=run_timestamp,
            )
        )

    return rows_out, quarantine_out
