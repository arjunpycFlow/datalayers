from pathlib import Path

from data_loader.vcf_headers import parse_vcf_headers

DATA_ROOT = Path("candidate_bundle/data")


def test_csq_field_order_batch_1():
    contract = parse_vcf_headers(DATA_ROOT / "batch_2026_01" / "S-0001.somatic.vcf")
    assert contract.csq_field_order == [
        "SYMBOL",
        "Consequence",
        "IMPACT",
        "HGVSc",
        "HGVSp",
        "EXON",
    ]


def test_csq_field_order_batch_2_has_mane_select():
    contract = parse_vcf_headers(DATA_ROOT / "batch_2026_02" / "S-0016.somatic.vcf")
    assert contract.csq_field_order == [
        "SYMBOL",
        "Consequence",
        "IMPACT",
        "HGVSc",
        "HGVSp",
        "EXON",
        "MANE_SELECT",
    ]


def test_info_declarations_captured():
    contract = parse_vcf_headers(DATA_ROOT / "batch_2026_01" / "S-0001.somatic.vcf")
    assert contract.info["HOTSPOT"].type == "Flag"
    assert contract.info["MAX_POP_AF"].type == "Float"


def test_sample_column_from_chrom_header():
    contract = parse_vcf_headers(DATA_ROOT / "batch_2026_01" / "S-0001.somatic.vcf")
    assert contract.sample_columns == ["S-0001"]
