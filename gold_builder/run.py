from dataclasses import dataclass
from pathlib import Path

import duckdb

from gold_builder.contracts import load_contract
from gold_builder.marts import cohort_gene_burden, sample_clinical_profile, variant_gene_lookup
from gold_builder.writer import connect, write_mart

CONTRACTS_ROOT = "config/gold_contracts"

# mart name -> (build function, grain kind, source-count query)
_MART_BUILDERS = {
    "gold_variant_gene_lookup_v1": (
        variant_gene_lookup.build, "row_level", "SELECT COUNT(*) FROM variant_calls",
    ),
    "gold_cohort_gene_burden_v1": (
        cohort_gene_burden.build, "aggregate", "SELECT COUNT(*) FROM variant_calls",
    ),
    "gold_sample_clinical_profile_v1": (
        sample_clinical_profile.build, "row_level", "SELECT COUNT(*) FROM samples",
    ),
}


class ReconciliationError(Exception):
    """A source row went missing between silver and a gold mart — a bug, not
    a data defect."""


class SchemaLeakError(Exception):
    """A `not_relevant` column showed up in a mart's actual schema — the
    minimization contract wasn't honored."""


@dataclass
class MartSummary:
    mart: str
    n_rows: int
    n_quarantined: int


@dataclass
class RunSummary:
    marts: list[MartSummary]
    gold_db_path: Path

    def render(self) -> str:
        lines = [f"gold-builder: -> {self.gold_db_path}"]
        for m in self.marts:
            lines.append(f"  {m.mart}: {m.n_rows} rows, {m.n_quarantined} quarantined")
        return "\n".join(lines)


def _check_reconciliation(mart_name: str, grain_kind: str, n_source_rows: int, rows: list[dict], quarantine: list) -> None:
    if grain_kind == "row_level":
        accounted = len(rows) + len(quarantine)
    else:  # aggregate
        accounted = sum(r["n_variants"] for r in rows) + len(quarantine)

    if accounted != n_source_rows:
        raise ReconciliationError(
            f"{mart_name}: {n_source_rows} source rows != {accounted} accounted for "
            f"(rows + quarantine)"
        )


def _check_not_relevant_absent(gold_con: duckdb.DuckDBPyConnection, contract) -> None:
    described = {row[0] for row in gold_con.execute(f"DESCRIBE {contract.schema}.{contract.mart}").fetchall()}
    leaked = described & set(contract.not_relevant)
    if leaked:
        raise SchemaLeakError(f"{contract.mart}: not_relevant column(s) {leaked} present in DESCRIBE output")


def discover_contract_files(contracts_root: str = CONTRACTS_ROOT) -> list[Path]:
    return sorted(Path(contracts_root).glob("*.yaml"))


def run(
    silver_db: str,
    out_root: str,
    mart_filter: list[str] | None,
    run_id: str,
    run_timestamp: str,
) -> RunSummary:
    silver_con = duckdb.connect(silver_db)
    gold_con = connect(out_root)

    summaries: list[MartSummary] = []

    for contract_path in discover_contract_files():
        contract = load_contract(str(contract_path))
        if mart_filter and contract.mart not in mart_filter:
            continue

        build_fn, grain_kind, count_query = _MART_BUILDERS[contract.mart]
        rows, quarantine = build_fn(silver_con, contract, run_id, run_timestamp)

        n_source_rows = silver_con.execute(count_query).fetchone()[0]
        _check_reconciliation(contract.mart, grain_kind, n_source_rows, rows, quarantine)

        write_mart(gold_con, contract, rows, quarantine)
        _check_not_relevant_absent(gold_con, contract)

        summaries.append(MartSummary(mart=contract.mart, n_rows=len(rows), n_quarantined=len(quarantine)))

    return RunSummary(marts=summaries, gold_db_path=Path(out_root, "gold.duckdb"))
