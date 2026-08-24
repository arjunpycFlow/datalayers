from pathlib import Path

import yaml

from gold_builder.models import ContractError, GoldContract

_VALID_TIERS = ("mandatory", "good_to_have", "okay_to_have", "not_relevant")


def load_contract(path: str) -> GoldContract:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    columns = data.get("columns", {})

    unknown_tiers = set(columns) - set(_VALID_TIERS)
    if unknown_tiers:
        raise ContractError(
            f"{data.get('mart', path)}: unknown column tier(s) {sorted(unknown_tiers)} "
            f"— valid tiers are {_VALID_TIERS}"
        )

    contract = GoldContract(
        mart=data["mart"],
        schema=data["schema"],
        grain=data["grain"],
        purpose=data["purpose"],
        mandatory=columns.get("mandatory", []),
        good_to_have=columns.get("good_to_have", []),
        okay_to_have=columns.get("okay_to_have", []),
        not_relevant=columns.get("not_relevant", []),
        filters=data.get("filters", []),
    )
    contract.validate()
    return contract
