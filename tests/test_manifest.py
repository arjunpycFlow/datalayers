from pathlib import Path

from data_loader.manifest import parse_manifest

DATA_ROOT = Path("candidate_bundle/data")


def test_batch_1_yields_14_usable_rows_s0011_quarantined():
    path = DATA_ROOT / "batch_2026_01" / "sample_manifest.csv"
    rows, quarantined, _ = parse_manifest(path, batch_id="batch_2026_01")

    usable_ids = {r.sample_id for r in rows}
    assert "S-0011" not in usable_ids
    assert len(rows) == 14

    conflicts = [q for q in quarantined if q.reason_code == "CONFLICTING_DUPLICATE"]
    assert len(conflicts) == 2  # both S-0011 rows
    assert all("S-0011" in c.raw_text for c in conflicts)
    assert "tumor_purity" in conflicts[0].reason_detail


def test_batch_2_has_library_prep_column():
    path = DATA_ROOT / "batch_2026_02" / "sample_manifest.csv"
    rows, _, _ = parse_manifest(path, batch_id="batch_2026_02")
    assert all(r.library_prep for r in rows)


def test_batch_1_has_no_library_prep():
    path = DATA_ROOT / "batch_2026_01" / "sample_manifest.csv"
    rows, _, _ = parse_manifest(path, batch_id="batch_2026_01")
    assert all(r.library_prep is None for r in rows)


def test_manifests_own_batch_id_column_is_captured():
    path = DATA_ROOT / "batch_2026_01" / "sample_manifest.csv"
    rows, _, _ = parse_manifest(path, batch_id="batch_2026_01")
    assert all(r.batch_id == "batch_2026_01" for r in rows)
