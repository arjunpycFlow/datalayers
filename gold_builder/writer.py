import re
from dataclasses import astuple
from pathlib import Path

import duckdb

from gold_builder.apply import GoldQuarantineRecord
from gold_builder.models import GoldContract

# Known column types across all marts. Row-level marts pass through silver's
# typed columns as-is; aggregate columns get their natural SQL type. Falls
# back to VARCHAR for anything not listed here — safe for the free-text
# columns, and a reminder to add a real type if a new numeric/boolean column
# is added to a contract later.
_KNOWN_TYPES = {
    "vaf": "DOUBLE",
    "qual": "DOUBLE",
    "collection_date": "DATE",
    "tumor_purity": "DOUBLE",
    "sex_concordant": "BOOLEAN",
    "is_ffpe": "BOOLEAN",
    "is_repeat_library": "BOOLEAN",
    "n_variants": "BIGINT",
    "n_distinct_samples": "BIGINT",
    "n_distinct_patients": "BIGINT",
    "n_samples_with_unknown_patient": "BIGINT",
    "n_hotspot_variants": "BIGINT",
    "mean_vaf": "DOUBLE",
}

_QUARANTINE_COLUMNS = [
    ("mart", "VARCHAR"),
    ("exclusion_reason_code", "VARCHAR"),
    ("exclusion_detail", "VARCHAR"),
    ("missing_columns", "VARCHAR[]"),
    ("row_identifier", "VARCHAR"),
    ("run_id", "VARCHAR"),
    ("run_timestamp", "VARCHAR"),
]


def _quarantine_table_name(mart: str) -> str:
    """gold_variant_gene_lookup_v1 -> gold_variant_gene_lookup_quarantine_v1
    (naming convention: the _quarantine suffix goes before the version)."""
    match = re.match(r"^(.*)_v(\d+)$", mart)
    if not match:
        return f"{mart}_quarantine"
    return f"{match.group(1)}_quarantine_v{match.group(2)}"


def write_mart(
    con: duckdb.DuckDBPyConnection,
    contract: GoldContract,
    rows: list[dict],
    quarantine: list[GoldQuarantineRecord],
) -> None:
    """Writes one mart into its declared schema (gold_open / gold_restricted).

    The schema split here is structural only, not enforced access control:
    embedded DuckDB has no GRANT/role system (confirmed — `GRANT SELECT ON
    SCHEMA ... TO ...` is a parser error, not an unsupported-but-parseable
    statement). Real access enforcement is the S3-to-S3 IAM mapping already
    described in working_contexts/ v2 §6.3 (a separate role per zone), not
    anything this local file can provide. Don't imply otherwise downstream.
    """
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {contract.schema}")

    table = f"{contract.schema}.{contract.mart}"
    col_defs = ", ".join(
        f'"{col}" {_KNOWN_TYPES.get(col, "VARCHAR")}' for col in contract.present_columns
    )
    con.execute(f"CREATE OR REPLACE TABLE {table} ({col_defs})")
    if rows:
        placeholders = ", ".join("?" for _ in contract.present_columns)
        values = [[row[col] for col in contract.present_columns] for row in rows]
        con.executemany(f"INSERT INTO {table} VALUES ({placeholders})", values)

    q_table = f"{contract.schema}.{_quarantine_table_name(contract.mart)}"
    q_col_defs = ", ".join(f'"{name}" {typ}' for name, typ in _QUARANTINE_COLUMNS)
    con.execute(f"CREATE OR REPLACE TABLE {q_table} ({q_col_defs})")
    if quarantine:
        q_placeholders = ", ".join("?" for _ in _QUARANTINE_COLUMNS)
        con.executemany(
            f"INSERT INTO {q_table} VALUES ({q_placeholders})",
            [astuple(q) for q in quarantine],
        )


def connect(out_root: str) -> duckdb.DuckDBPyConnection:
    db_path = Path(out_root, "gold.duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))
