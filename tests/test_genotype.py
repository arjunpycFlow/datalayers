from silver_builder.genotype import extract_genotype


def test_extract_genotype_standard_order():
    gt, ad, dp, vaf = extract_genotype(
        ["GT", "AD", "DP", "VAF"], ["0/1", "78,40", "118", "0.3390"]
    )
    assert gt == "0/1"
    assert ad == "78,40"
    assert dp == 118
    assert vaf == 0.3390


def test_extract_genotype_reordered_keys_is_name_based_not_positional():
    # Same values, but FORMAT declares them in a different order —
    # extraction must still land in the right named fields.
    gt, ad, dp, vaf = extract_genotype(
        ["VAF", "DP", "AD", "GT"], ["0.3390", "118", "78,40", "0/1"]
    )
    assert gt == "0/1"
    assert ad == "78,40"
    assert dp == 118
    assert vaf == 0.3390


def test_extract_genotype_missing_key_is_none():
    gt, ad, dp, vaf = extract_genotype(["GT"], ["0/1"])
    assert gt == "0/1"
    assert ad is None
    assert dp is None
    assert vaf is None
