from silver_builder.normalize import normalize_af


def extract_genotype(
    format_keys: list[str], genotype_values: list[str]
) -> tuple[str | None, str | None, int | None, float | None]:
    """Extract (gt, ad, dp, vaf) by matching declared FORMAT key names, not
    position — which FORMAT keys exist, and in what order, is declared
    per-file and not guaranteed by contract, even though it's identical
    (GT:AD:DP:VAF) in both batches observed so far.

    vaf is normalized via normalize_af — batch_2026_02's VAF is on a x100
    scale (confirmed against source, see normalize_af's docstring)."""

    fields = dict(zip(format_keys, genotype_values))

    gt = fields.get("GT")
    ad = fields.get("AD")

    dp_raw = fields.get("DP")
    dp = int(dp_raw) if dp_raw not in (None, "") else None

    vaf = normalize_af(fields.get("VAF"))

    return gt, ad, dp, vaf
