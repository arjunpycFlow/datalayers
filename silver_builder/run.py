from dataclasses import dataclass
from pathlib import Path

import duckdb

from silver_builder.crosswalks import load_crosswalk
from silver_builder.discover import resolve_data_files
from silver_builder.models import SilverQuarantine, SilverSample
from silver_builder.transform import transform_rows
from silver_builder.writer import write_silver

_CROSSWALK_NAMES = ["tissue", "sequencing_platform", "library_prep", "qc_status", "sex"]


class ReconciliationError(Exception):
    """A sample went missing between bronze input and silver output — a bug,
    not a data defect."""


@dataclass
class RunSummary:
    n_bronze_data_files: int
    n_bronze_rows: int
    n_samples: int
    n_variant_calls: int
    n_quarantined: int
    db_path: Path

    def render(self) -> str:
        return (
            f"silver_builder: read {self.n_bronze_rows} rows from "
            f"{self.n_bronze_data_files} bronze file(s) -> "
            f"{self.n_samples} samples, {self.n_variant_calls} variant calls, "
            f"{self.n_quarantined} quarantined -> {self.db_path}"
        )


def _check_reconciliation(
    bronze_sample_ids: set[str],
    silver_samples: list[SilverSample],
    silver_quarantine: list[SilverQuarantine],
) -> None:
    accounted = {s.sample_id for s in silver_samples} | {
        q.sample_id for q in silver_quarantine
    }
    missing = bronze_sample_ids - accounted
    if missing:
        raise ReconciliationError(
            f"{len(missing)} sample(s) present in bronze but neither written to "
            f"silver.samples nor silver.quarantine: {sorted(missing)}"
        )


def _load_crosswalks() -> dict[str, dict[str, str]]:
    return {name: load_crosswalk(f"config/crosswalks/{name}.yaml") for name in _CROSSWALK_NAMES}


def _read_bronze_rows(data_files: list[Path]) -> list[dict]:
    con = duckdb.connect()
    rows: list[dict] = []
    for f in data_files:
        cur = con.execute(f"SELECT * FROM read_parquet('{f}')")
        cols = [d[0] for d in cur.description]
        rows.extend(dict(zip(cols, r)) for r in cur.fetchall())
    return rows


def run(
    bronze_data_root: str,
    explicit_data_files: list[str] | None,
    out_root: str,
    run_id: str,
    run_timestamp: str,
) -> RunSummary:
    data_files = resolve_data_files(bronze_data_root, explicit_data_files)
    if not data_files:
        raise FileNotFoundError(
            "no bronze data files found (neither auto-discovered nor given explicitly)"
        )

    rows = _read_bronze_rows(data_files)
    crosswalks = _load_crosswalks()
    samples, variant_calls, quarantine = transform_rows(rows, crosswalks, run_id, run_timestamp)

    bronze_sample_ids = {r["sample_id"] for r in rows}
    _check_reconciliation(bronze_sample_ids, samples, quarantine)

    db_path = write_silver(samples, variant_calls, quarantine, out_root)

    return RunSummary(
        n_bronze_data_files=len(data_files),
        n_bronze_rows=len(rows),
        n_samples=len(samples),
        n_variant_calls=len(variant_calls),
        n_quarantined=len(quarantine),
        db_path=db_path,
    )
