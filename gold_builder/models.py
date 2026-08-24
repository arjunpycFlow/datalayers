from dataclasses import dataclass, field

_VALID_TIERS = ("mandatory", "good_to_have", "okay_to_have", "not_relevant")


class ContractError(Exception):
    """A gold contract YAML is malformed — caught at load time, not silently
    accepted."""


@dataclass
class GoldContract:
    mart: str
    schema: str
    grain: str
    purpose: str
    mandatory: list[str] = field(default_factory=list)
    good_to_have: list[str] = field(default_factory=list)
    okay_to_have: list[str] = field(default_factory=list)
    not_relevant: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)

    @property
    def present_columns(self) -> list[str]:
        """Columns that appear in this mart's output schema — everything
        except `not_relevant`, which is dropped from the schema entirely."""
        return [*self.mandatory, *self.good_to_have, *self.okay_to_have]

    def validate(self) -> None:
        seen: dict[str, str] = {}
        for tier in _VALID_TIERS:
            for column in getattr(self, tier):
                if column in seen:
                    raise ContractError(
                        f"{self.mart}: column {column!r} listed in both "
                        f"{seen[column]!r} and {tier!r} — a column may only be in one tier"
                    )
                seen[column] = tier
