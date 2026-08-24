from dataclasses import astuple, fields
from pathlib import Path

import duckdb

from silver_builder.models import SilverQuarantine, SilverSample, SilverVariantCall

_SAMPLE_COLUMNS = [
    ("sample_id", "VARCHAR"),
    ("patient_id", "VARCHAR"),
    ("batch_id", "VARCHAR"),
    ("collection_date", "DATE"),
    ("collection_date_raw", "VARCHAR"),
    ("tissue", "VARCHAR"),
    ("diagnosis", "VARCHAR"),
    ("disease_group", "VARCHAR"),
    ("tumor_purity", "DOUBLE"),
    ("sex_reported", "VARCHAR"),
    ("sex_inferred", "VARCHAR"),
    ("sex_concordant", "BOOLEAN"),
    ("sequencing_platform", "VARCHAR"),
    ("qc_status", "VARCHAR"),
    ("library_prep", "VARCHAR"),
    ("is_ffpe", "BOOLEAN"),
    ("is_repeat_library", "BOOLEAN"),
    ("notes", "VARCHAR"),
    ("has_variant_data", "BOOLEAN"),
    ("bronze_source_file", "VARCHAR"),
    ("bronze_run_id", "VARCHAR"),
    ("bronze_run_timestamp", "VARCHAR"),
]

_VARIANT_CALL_COLUMNS = [
    ("sample_id", "VARCHAR"),
    ("chrom", "VARCHAR"),
    ("pos", "VARCHAR"),
    ("ref", "VARCHAR"),
    ("alt", "VARCHAR"),
    ("id", "VARCHAR"),
    ("qual", "DOUBLE"),
    ("filter", "VARCHAR"),
    ("caller", "VARCHAR"),
    ("max_pop_af", "DOUBLE"),
    ("hotspot", "BOOLEAN"),
    ("gene_symbol", "VARCHAR"),
    ("consequence", "VARCHAR"),
    ("impact", "VARCHAR"),
    ("hgvsc", "VARCHAR"),
    ("hgvsp", "VARCHAR"),
    ("exon", "VARCHAR"),
    ("mane_select", "VARCHAR"),
    ("ccf", "DOUBLE"),
    ("gnomad_af_popmax", "DOUBLE"),
    ("gt", "VARCHAR"),
    ("ad", "VARCHAR"),
    ("dp", "INTEGER"),
    ("vaf", "DOUBLE"),
    ("pipeline_version", "VARCHAR"),
    ("bronze_source_file", "VARCHAR"),
    ("bronze_run_id", "VARCHAR"),
    ("bronze_run_timestamp", "VARCHAR"),
]

_QUARANTINE_COLUMNS = [
    ("entity_type", "VARCHAR"),
    ("sample_id", "VARCHAR"),
    ("field_name", "VARCHAR"),
    ("raw_value", "VARCHAR"),
    ("reason_code", "VARCHAR"),
    ("reason_detail", "VARCHAR"),
    ("run_id", "VARCHAR"),
    ("run_timestamp", "VARCHAR"),
]


def _assert_column_order_matches(dataclass_type, columns: list[tuple[str, str]]) -> None:
    dataclass_fields = [f.name for f in fields(dataclass_type)]
    column_names = [name for name, _ in columns]
    if dataclass_fields != column_names:
        raise AssertionError(
            f"{dataclass_type.__name__} field order {dataclass_fields} != "
            f"writer column order {column_names} — astuple() relies on these matching"
        )


_assert_column_order_matches(SilverSample, _SAMPLE_COLUMNS)
_assert_column_order_matches(SilverVariantCall, _VARIANT_CALL_COLUMNS)
_assert_column_order_matches(SilverQuarantine, _QUARANTINE_COLUMNS)


def _create_and_insert(con, table_name: str, rows: list, columns: list[tuple[str, str]]) -> None:
    col_defs = ", ".join(f'"{name}" {typ}' for name, typ in columns)
    placeholders = ", ".join("?" for _ in columns)
    con.execute(f"CREATE OR REPLACE TABLE {table_name} ({col_defs})")
    if rows:
        con.executemany(
            f"INSERT INTO {table_name} VALUES ({placeholders})",
            [astuple(row) for row in rows],
        )


def write_silver(
    samples: list[SilverSample],
    variant_calls: list[SilverVariantCall],
    quarantine: list[SilverQuarantine],
    out_root: str,
) -> Path:
    """Full rebuild every run — CREATE OR REPLACE, not an incremental merge.
    Deterministic: same inputs always produce the same table contents."""

    db_path = Path(out_root, "silver.duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    try:
        _create_and_insert(con, "samples", samples, _SAMPLE_COLUMNS)
        _create_and_insert(con, "variant_calls", variant_calls, _VARIANT_CALL_COLUMNS)
        _create_and_insert(con, "quarantine", quarantine, _QUARANTINE_COLUMNS)

        con.execute(
            """
            CREATE OR REPLACE TABLE patients AS
            SELECT patient_id, COUNT(*) AS n_samples
            FROM samples
            WHERE patient_id IS NOT NULL
            GROUP BY patient_id
            """
        )

        con.execute(
            """
            CREATE OR REPLACE TABLE batches AS
            SELECT
                s.batch_id,
                COUNT(DISTINCT s.sample_id) AS n_samples,
                COUNT(v.sample_id) AS n_variant_calls,
                STRING_AGG(DISTINCT v.pipeline_version, ', ') AS pipeline_versions
            FROM samples s
            LEFT JOIN variant_calls v ON v.sample_id = s.sample_id
            WHERE s.batch_id IS NOT NULL
            GROUP BY s.batch_id
            """
        )
    finally:
        con.close()

    return db_path
