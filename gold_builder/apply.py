from dataclasses import dataclass


@dataclass
class GoldQuarantineRecord:
    """A row that didn't meet a specific mart's contract. Not bad data — data
    that failed *this mart's* completeness contract; it may be present and
    valid in a different mart."""

    mart: str
    exclusion_reason_code: str
    exclusion_detail: str
    missing_columns: list[str]
    row_identifier: str
    run_id: str
    run_timestamp: str


def apply_contract(
    contract, row: dict, row_identifier: str, run_id: str, run_timestamp: str
) -> tuple[dict | None, GoldQuarantineRecord | None]:
    """Row-level contract application, grain-agnostic: works for any
    row-level mart (not the aggregate mart, which has its own logic).

    Only a `mandatory`-tier NULL excludes the row. `good_to_have`/
    `okay_to_have` NULLs never exclude — the row lands with that field NULL.
    `not_relevant` columns are dropped from the output entirely, not merely
    left in as NULL.
    """
    missing = [col for col in contract.mandatory if row.get(col) is None]
    if missing:
        return None, GoldQuarantineRecord(
            mart=contract.mart,
            exclusion_reason_code="MISSING_MANDATORY_COLUMN",
            exclusion_detail=f"required column(s) {missing} are NULL",
            missing_columns=missing,
            row_identifier=row_identifier,
            run_id=run_id,
            run_timestamp=run_timestamp,
        )

    output_row = {col: row.get(col) for col in contract.present_columns}
    return output_row, None
