from dataclasses import astuple, fields
from pathlib import Path

import duckdb

from data_loader.models import DataRow, QuarantineRow

_DATA_COLUMNS = [
    ("sample_id", "VARCHAR"),
    ("patient_id", "VARCHAR"),
    ("batch_id", "VARCHAR"),
    ("collection_date", "VARCHAR"),
    ("tissue", "VARCHAR"),
    ("diagnosis", "VARCHAR"),
    ("disease_group", "VARCHAR"),
    ("tumor_purity", "VARCHAR"),
    ("sex_reported", "VARCHAR"),
    ("sex_inferred", "VARCHAR"),
    ("sequencing_platform", "VARCHAR"),
    ("qc_status", "VARCHAR"),
    ("notes", "VARCHAR"),
    ("library_prep", "VARCHAR"),
    ("chrom", "VARCHAR"),
    ("pos", "VARCHAR"),
    ("id", "VARCHAR"),
    ("ref", "VARCHAR"),
    ("alt", "VARCHAR"),
    ("qual", "VARCHAR"),
    ("filter", "VARCHAR"),
    ("info", "MAP(VARCHAR, VARCHAR)"),
    ("format_keys", "VARCHAR[]"),
    ("genotype_values", "VARCHAR[]"),
    ("vcf_source_file", "VARCHAR"),
    ("manifest_source_file", "VARCHAR"),
    ("pipeline_version", "VARCHAR"),
    ("run_id", "VARCHAR"),
    ("run_timestamp", "VARCHAR"),
]

_QUARANTINE_COLUMNS = [
    ("batch_id", "VARCHAR"),
    ("entity_type", "VARCHAR"),
    ("source_file", "VARCHAR"),
    ("source_line_no", "VARCHAR"),
    ("raw_text", "VARCHAR"),
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


_assert_column_order_matches(DataRow, _DATA_COLUMNS)
_assert_column_order_matches(QuarantineRow, _QUARANTINE_COLUMNS)


def _write_parquet(rows, columns: list[tuple[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    col_defs = ", ".join(f'"{name}" {typ}' for name, typ in columns)
    placeholders = ", ".join("?" for _ in columns)

    con = duckdb.connect()
    con.execute(f"CREATE TABLE rows ({col_defs})")
    if rows:
        con.executemany(
            f"INSERT INTO rows VALUES ({placeholders})",
            [astuple(row) for row in rows],
        )
    con.execute(
        f"COPY rows TO '{out_path}' (FORMAT parquet, COMPRESSION zstd)"
    )
    con.close()


def write_bronze(
    data_rows: list[DataRow],
    quarantine_rows: list[QuarantineRow],
    out_root: str,
    batch_id: str,
    run_timestamp: str,
) -> tuple[Path, Path]:
    """Write both bronze outputs as new, timestamped files — never overwrite."""

    data_path = Path(out_root, "bronze", "data", batch_id, f"data_{run_timestamp}.parquet")
    quarantine_path = Path(
        out_root, "bronze", "quarantine", batch_id, f"quarantine_{run_timestamp}.parquet"
    )

    if data_path.exists() or quarantine_path.exists():
        raise FileExistsError(
            f"refusing to overwrite existing bronze output for this run: "
            f"{data_path} / {quarantine_path}"
        )

    _write_parquet(data_rows, _DATA_COLUMNS, data_path)
    _write_parquet(quarantine_rows, _QUARANTINE_COLUMNS, quarantine_path)

    return data_path, quarantine_path
