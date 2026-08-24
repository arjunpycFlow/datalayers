from pathlib import Path

from data_loader.vcf_headers import parse_vcf_headers
from data_loader.vcf_rows import parse_vcf_rows

DATA_ROOT = Path("candidate_bundle/data")
FIXTURES = Path("tests/fixtures")


def test_clean_file_produces_no_quarantine():
    path = DATA_ROOT / "batch_2026_01" / "S-0001.somatic.vcf"
    contract = parse_vcf_headers(path)
    rows, quarantined, _ = parse_vcf_rows(path, contract)
    assert quarantined == []
    assert len(rows) > 0


def test_hotspot_flag_parses_to_true_not_a_crash():
    path = DATA_ROOT / "batch_2026_01" / "S-0001.somatic.vcf"
    contract = parse_vcf_headers(path)
    rows, _, _ = parse_vcf_rows(path, contract)
    hotspot_rows = [r for r in rows if r.info.get("HOTSPOT") is not None]
    assert hotspot_rows
    assert hotspot_rows[0].info["HOTSPOT"] == "true"


def test_truncated_final_line_quarantined_valid_rows_still_parsed():
    path = FIXTURES / "truncated_sample.vcf"
    contract = parse_vcf_headers(path)
    rows, quarantined, _ = parse_vcf_rows(path, contract)

    assert len(quarantined) == 1
    assert quarantined[0].reason_code == "MALFORMED_VCF_LINE"
    assert quarantined[0].raw_text.startswith("chr4\t123456")

    assert len(rows) == 4
    assert all(r.chrom != "chr4" for r in rows)


def test_csq_split_into_declared_subfields():
    path = DATA_ROOT / "batch_2026_01" / "S-0001.somatic.vcf"
    contract = parse_vcf_headers(path)
    rows, _, _ = parse_vcf_rows(path, contract)
    row = rows[0]
    assert row.info["CSQ_SYMBOL"] == "ARID1A"
    assert row.info["CSQ_Consequence"] == "missense_variant"
