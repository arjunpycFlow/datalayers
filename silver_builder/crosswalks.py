from pathlib import Path

import yaml

from silver_builder.errors import NormalizationError


def load_crosswalk(path: str) -> dict[str, str]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data["mappings"]


def apply_crosswalk(
    raw: str | None, mappings: dict[str, str], field_name: str
) -> str | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    if raw in mappings:
        return mappings[raw]

    raise NormalizationError(
        "UNMAPPED_VOCABULARY_TERM",
        f"{field_name} value {raw!r} is not in the crosswalk",
    )
