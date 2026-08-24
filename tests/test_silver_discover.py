from pathlib import Path

from silver_builder.discover import resolve_data_files


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_auto_discovery_picks_latest_timestamp_per_batch(tmp_path):
    bronze_data_root = tmp_path / "bronze_data"
    _touch(bronze_data_root / "batch_2026_01" / "data_20260101T000000.parquet")
    later_01 = bronze_data_root / "batch_2026_01" / "data_20260102T000000.parquet"
    _touch(later_01)
    _touch(bronze_data_root / "batch_2026_02" / "data_20260101T000000.parquet")
    later_02 = bronze_data_root / "batch_2026_02" / "data_20260103T000000.parquet"
    _touch(later_02)

    resolved = resolve_data_files(str(bronze_data_root), explicit_files=None)

    assert sorted(resolved) == sorted([later_01, later_02])


def test_explicit_data_files_override_auto_discovery(tmp_path):
    bronze_data_root = tmp_path / "bronze_data"
    _touch(bronze_data_root / "batch_2026_01" / "data_20260102T000000.parquet")

    explicit = tmp_path / "somewhere_else" / "custom.parquet"
    _touch(explicit)

    resolved = resolve_data_files(str(bronze_data_root), explicit_files=[str(explicit)])

    assert resolved == [explicit]


def test_no_files_found_returns_empty_list(tmp_path):
    resolved = resolve_data_files(str(tmp_path / "nonexistent"), explicit_files=None)
    assert resolved == []
