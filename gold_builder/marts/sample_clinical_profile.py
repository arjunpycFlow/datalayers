import duckdb

from gold_builder.apply import GoldQuarantineRecord, apply_contract
from gold_builder.models import GoldContract

SOURCE_QUERY = """
    SELECT sample_id, patient_id, tissue, diagnosis, collection_date, tumor_purity,
           sex_reported, sex_inferred, sex_concordant, qc_status, sequencing_platform,
           library_prep, notes, is_ffpe, is_repeat_library
    FROM samples
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
        row_id = f"sample_id={row['sample_id']}"
        output, quarantine = apply_contract(contract, row, row_id, run_id, run_timestamp)
        if output is not None:
            rows_out.append(output)
        if quarantine is not None:
            quarantine_out.append(quarantine)

    return rows_out, quarantine_out
