import pytest

from silver_builder.models import SilverQuarantine, SilverSample
from silver_builder.run import ReconciliationError, _check_reconciliation


def _sample(sample_id):
    return SilverSample(
        sample_id=sample_id, patient_id=None, batch_id=None, collection_date=None,
        collection_date_raw=None, tissue=None, diagnosis=None, disease_group=None,
        tumor_purity=None, sex_reported=None, sex_inferred=None, sex_concordant=None,
        sequencing_platform=None, qc_status=None, library_prep=None, is_ffpe=False,
        is_repeat_library=False, notes=None, has_variant_data=True,
        bronze_source_file=None, bronze_run_id="", bronze_run_timestamp="",
    )


def _quarantine(sample_id):
    return SilverQuarantine(
        entity_type="sample", sample_id=sample_id, field_name="tissue",
        raw_value="x", reason_code="UNMAPPED_VOCABULARY_TERM", reason_detail="",
        run_id="", run_timestamp="",
    )


def test_reconciliation_trips_when_a_sample_is_unaccounted_for():
    with pytest.raises(ReconciliationError):
        _check_reconciliation(
            bronze_sample_ids={"S-0001", "S-0002", "S-0003"},
            silver_samples=[_sample("S-0001"), _sample("S-0002")],
            silver_quarantine=[],  # S-0003 neither written nor quarantined
        )


def test_reconciliation_passes_when_every_sample_accounted_for():
    _check_reconciliation(
        bronze_sample_ids={"S-0001", "S-0002", "S-0003"},
        silver_samples=[_sample("S-0001"), _sample("S-0002")],
        silver_quarantine=[_quarantine("S-0003")],
    )  # no raise
