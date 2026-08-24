import pytest

from silver_builder.crosswalks import apply_crosswalk, load_crosswalk
from silver_builder.errors import NormalizationError

TISSUE = load_crosswalk("config/crosswalks/tissue.yaml")
PLATFORM = load_crosswalk("config/crosswalks/sequencing_platform.yaml")
LIBRARY_PREP = load_crosswalk("config/crosswalks/library_prep.yaml")
QC_STATUS = load_crosswalk("config/crosswalks/qc_status.yaml")
SEX = load_crosswalk("config/crosswalks/sex.yaml")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("lung", "Lung"),
        ("LUNG", "Lung"),
        ("Lung", "Lung"),
        ("breast", "Breast"),
        ("Breast", "Breast"),
        ("COLON", "Colon"),
        ("Colon", "Colon"),
        ("STOMACH", "Stomach"),
        ("Stomach", "Stomach"),
        ("pancreas", "Pancreas"),
        ("Pancreas", "Pancreas"),
    ],
)
def test_tissue_crosswalk_covers_all_observed_values(raw, expected):
    assert apply_crosswalk(raw, TISSUE, "tissue") == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("NovaSeq X", "NovaSeq X"),
        ("novaseq 6000", "NovaSeq 6000"),
        ("NovaSeq 6000", "NovaSeq 6000"),
        ("NovaSeq6000", "NovaSeq 6000"),
    ],
)
def test_platform_crosswalk_covers_all_observed_values(raw, expected):
    assert apply_crosswalk(raw, PLATFORM, "sequencing_platform") == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("TruSeq DNA PCR-Free", "TruSeq DNA PCR-Free"),
        ("truseq dna pcr-free", "TruSeq DNA PCR-Free"),
        ("KAPA HyperPrep", "KAPA HyperPrep"),
    ],
)
def test_library_prep_crosswalk_covers_all_observed_values(raw, expected):
    assert apply_crosswalk(raw, LIBRARY_PREP, "library_prep") == expected


def test_qc_status_pass_case_variants():
    assert apply_crosswalk("PASS", QC_STATUS, "qc_status") == "PASS"
    assert apply_crosswalk("pass", QC_STATUS, "qc_status") == "PASS"


def test_qc_status_empty_is_none_not_unmapped():
    assert apply_crosswalk("", QC_STATUS, "qc_status") is None
    assert apply_crosswalk(None, QC_STATUS, "qc_status") is None


@pytest.mark.parametrize(
    "raw,expected",
    [("m", "M"), ("M", "M"), ("male", "M"), ("Male", "M"),
     ("f", "F"), ("F", "F"), ("female", "F"), ("Female", "F")],
)
def test_sex_crosswalk_covers_all_observed_values(raw, expected):
    assert apply_crosswalk(raw, SEX, "sex_reported") == expected


def test_s0007_discordant_sex_normalizes_independently_without_erroring():
    # S-0007: sex_reported=Female, sex_inferred=M — normalize independently,
    # never reconciled to one value.
    assert apply_crosswalk("Female", SEX, "sex_reported") == "F"
    assert apply_crosswalk("M", SEX, "sex_inferred") == "M"


def test_unmapped_value_raises():
    with pytest.raises(NormalizationError) as exc_info:
        apply_crosswalk("Kidney", TISSUE, "tissue")
    assert exc_info.value.reason_code == "UNMAPPED_VOCABULARY_TERM"
