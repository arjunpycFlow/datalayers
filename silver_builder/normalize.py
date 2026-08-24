from datetime import date, datetime

from silver_builder.crosswalks import apply_crosswalk
from silver_builder.errors import NormalizationError

# DD/MM only, deliberately — never MM/DD. A slash-ambiguous value like
# "04/01/2026" is genuinely ambiguous on its own, but every batch observed so
# far is internally DD/MM-consistent with its own batch window (v1 finding).
# This is a documented assumption, not a fact — it will need revisiting if a
# future batch's dates don't fit that window.
_DATE_FORMATS = ["%b %d %Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"]


def normalize_purity(raw: str | None) -> float | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    try:
        if raw.endswith("%"):
            value = float(raw[:-1]) / 100
        else:
            value = float(raw)
    except ValueError:
        raise NormalizationError(
            "PURITY_OUT_OF_RANGE", f"tumor_purity {raw!r} is not a parseable number"
        )

    if not (0 <= value <= 1):
        raise NormalizationError(
            "PURITY_OUT_OF_RANGE",
            f"tumor_purity {raw!r} normalizes to {value}, outside [0, 1]",
        )
    return value


def normalize_af(raw: str | None) -> float | None:
    """Normalize a VCF-native allele-frequency-like field (VAF, MAX_POP_AF,
    GNOMAD_AF_POPMAX, CCF) to a [0,1] fraction.

    Unlike tumor_purity (a free-text manifest field where a bare "63" is
    genuinely ambiguous — typo vs. an unmarked percent — so it quarantines),
    these are numeric VCF fields with no "%" marker ever observed, and the
    quantity is definitionally bounded [0,1]. A parsed value > 1 has no valid
    alternate reading, so auto-correcting by /100 is not a guess — it's the
    only interpretation consistent with what the field means.

    Confirmed against real data: batch_2026_02's VAF is entirely on a x100
    scale (verified via AD/DP: 32/57=0.5614, file's VAF=56.14). MAX_POP_AF,
    GNOMAD_AF_POPMAX, and CCF do NOT currently have this problem in either
    batch (re-checked with a scientific-notation-aware regex after an earlier
    check falsely flagged outliers — those were `9.6e-06` truncated to `9.6`
    by a regex that didn't handle `e-06`, not real data) — normalize_af is
    still applied to them for consistency/future-proofing, since it's a
    no-op for any value already in [0,1].
    """
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    value = float(raw)
    if value > 1:
        value = value / 100
    return value


def normalize_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    # Unparseable is a value-level defect: NULL + implicitly flagged by the
    # NULL itself, never quarantined and never guessed at.
    return None


def normalize_sex(
    raw: str | None, sex_crosswalk: dict[str, str], field_name: str
) -> str | None:
    """sex_reported and sex_inferred are normalized independently — never
    reconciled against each other. A discordance is a QC finding, not a
    formatting defect."""
    return apply_crosswalk(raw, sex_crosswalk, field_name)


def derive_notes_flags(raw: str | None) -> tuple[bool, bool]:
    """(is_ffpe, is_repeat_library) — keyword detection against the two
    clinically meaningful terms observed in the notes column."""
    text = (raw or "").lower()
    return "ffpe" in text, "repeat library" in text
