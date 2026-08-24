import pytest

from data_loader.run import ReconciliationError, _check_reconciliation, run


def test_reconciliation_trips_when_a_record_goes_unaccounted_for():
    with pytest.raises(ReconciliationError):
        _check_reconciliation(
            manifest_lines_read=16,
            manifest_usable=14,
            manifest_quarantined=1,  # should be 2 — one record silently dropped
            manifest_duplicates_collapsed=0,
            vcf_lines_read=100,
            vcf_lines_quarantined=0,
        )


def test_reconciliation_passes_when_everything_is_accounted_for():
    _check_reconciliation(
        manifest_lines_read=16,
        manifest_usable=14,
        manifest_quarantined=2,
        manifest_duplicates_collapsed=0,
        vcf_lines_read=100,
        vcf_lines_quarantined=1,
    )  # no raise


def test_end_to_end_run_batch_2026_01(tmp_path):
    summary = run(
        batch_id="batch_2026_01",
        data_root="candidate_bundle/data",
        out_root=str(tmp_path),
        run_id="test-run",
        run_timestamp="20260101T000000",
    )
    assert summary.manifest_lines_read == 16
    assert summary.manifest_duplicates_collapsed == 0
    assert summary.manifest_quarantined == 2  # both S-0011 rows
    assert summary.data_rows_written > 0
    assert summary.data_path.exists()
    assert summary.quarantine_path.exists()


def test_end_to_end_run_batch_2026_02_handles_truncation(tmp_path):
    summary = run(
        batch_id="batch_2026_02",
        data_root="candidate_bundle/data",
        out_root=str(tmp_path),
        run_id="test-run",
        run_timestamp="20260101T000000",
    )
    assert summary.vcf_quarantined == 1  # S-0020's truncated line
    assert summary.data_rows_written > 0
