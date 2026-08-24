from pathlib import Path


def discover_bronze_data_files(bronze_data_root: str) -> list[Path]:
    """One file per `<batch_id>/` subdirectory: the lexicographically-latest
    `data_*.parquet` (the timestamp format sorts chronologically)."""

    root = Path(bronze_data_root)
    if not root.is_dir():
        return []

    files: list[Path] = []
    for batch_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        candidates = sorted(batch_dir.glob("data_*.parquet"))
        if candidates:
            files.append(candidates[-1])
    return files


def resolve_data_files(
    bronze_data_root: str, explicit_files: list[str] | None
) -> list[Path]:
    """Explicit files, if given, replace auto-discovery entirely."""

    if explicit_files:
        return [Path(p) for p in explicit_files]
    return discover_bronze_data_files(bronze_data_root)
