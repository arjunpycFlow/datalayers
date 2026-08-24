import duckdb

from gold_builder.apply import GoldQuarantineRecord, apply_contract
from gold_builder.models import GoldContract

SOURCE_QUERY = """
    SELECT s.sample_id, v.chrom, v.pos, v.ref, v.alt, v.gene_symbol, s.tissue,
           v.consequence, v.impact, s.diagnosis, v.filter, v.vaf, v.hgvsp, v.exon,
           s.qc_status, s.disease_group, s.collection_date, s.tumor_purity,
           s.notes, s.sequencing_platform, s.library_prep, s.patient_id
    FROM variant_calls v JOIN samples s USING (sample_id)
"""


def build(
    con: duckdb.DuckDBPyConnection,
    contract: GoldContract,
    run_id: str,
    run_timestamp: str,
) -> tuple[list[dict], list[GoldQuarantineRecord]]:
    cur = con.execute(SOURCE_QUERY)
    cols = [d[0] for d in cur.description]

    rows_out: list[dict] = []
    quarantine_out: list[GoldQuarantineRecord] = []

    for record in cur.fetchall():
        row = dict(zip(cols, record))
        row_id = (
            f"sample_id={row['sample_id']},chrom={row['chrom']},pos={row['pos']},"
            f"ref={row['ref']},alt={row['alt']}"
        )
        output, quarantine = apply_contract(contract, row, row_id, run_id, run_timestamp)
        if output is not None:
            rows_out.append(output)
        if quarantine is not None:
            quarantine_out.append(quarantine)

    return rows_out, quarantine_out
