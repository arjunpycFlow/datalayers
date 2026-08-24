from datetime import date

import pytest

from silver_builder.crosswalks import load_crosswalk
from silver_builder.errors import NormalizationError
from silver_builder.normalize import (
    derive_notes_flags,
    normalize_af,
    normalize_date,
    normalize_purity,
    normalize_sex,
)

SEX_CROSSWALK = load_crosswalk("config/crosswalks/sex.yaml")


def test_purity_percent_string():
    assert normalize_purity("63%") == pytest.approx(0.63)


def test_purity_plain_fraction_string():
    assert normalize_purity("0.32") == pytest.approx(0.32)


def test_purity_missing_is_none():
    assert normalize_purity(None) is None
    assert normalize_purity("") is None


def test_purity_out_of_range_raises():
    with pytest.raises(NormalizationError) as exc_info:
        normalize_purity("630%")
    assert exc_info.value.reason_code == "PURITY_OUT_OF_RANGE"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Jan 5 2026", date(2026, 1, 5)),
        ("2026-01-07", date(2026, 1, 7)),
        ("2026/01/09", date(2026, 1, 9)),
        ("17/01/2026", date(2026, 1, 17)),
        ("04/01/2026", date(2026, 1, 4)),  # DD/MM assumption, documented
        ("Feb 14 2026", date(2026, 2, 14)),
    ],
)
def test_date_all_observed_formats(raw, expected):
    assert normalize_date(raw) == expected


def test_date_missing_is_none():
    assert normalize_date(None) is None
    assert normalize_date("") is None


def test_date_unparseable_is_none_not_quarantined():
    assert normalize_date("not a date") is None


def test_s0007_sex_normalizes_independently():
    # S-0007: sex_reported=Female, sex_inferred=M — must not error or reconcile.
    assert normalize_sex("Female", SEX_CROSSWALK, "sex_reported") == "F"
    assert normalize_sex("M", SEX_CROSSWALK, "sex_inferred") == "M"


def test_af_already_a_fraction_is_unchanged():
    # batch_2026_01 VAF — real value, confirmed via source grep
    assert normalize_af("0.3390") == pytest.approx(0.339)


def test_af_percentage_scale_is_corrected_to_fraction():
    # batch_2026_02 S-0016 first variant — confirmed AD=25,32 DP=57 -> 32/57=0.5614,
    # and the file's raw VAF is 56.14 (exactly x100). Real drift, not synthetic.
    assert normalize_af("56.14") == pytest.approx(0.5614)


def test_af_generic_over_1_value_is_corrected():
    # Synthetic — real MAX_POP_AF/GNOMAD_AF_POPMAX/CCF values in both batches
    # are already in [0,1] (an earlier check found apparent outliers, but that
    # was a regex bug truncating scientific notation like "9.6e-06" to "9.6",
    # not real data). This just proves the >1 correction path works generically.
    assert normalize_af("9.6") == pytest.approx(0.096)


def test_af_scientific_notation_small_value_unchanged():
    # The actual real-data case that produced the false alarm above.
    assert normalize_af("9.6e-06") == pytest.approx(0.0000096)


def test_af_missing_is_none():
    assert normalize_af(None) is None
    assert normalize_af("") is None


def test_notes_flags():
    assert derive_notes_flags("FFPE block") == (True, False)
    assert derive_notes_flags("repeat library") == (False, True)
    assert derive_notes_flags(None) == (False, False)
    assert derive_notes_flags("") == (False, False)
