from pathlib import Path

import pytest

from gold_builder.contracts import load_contract
from gold_builder.models import ContractError

FIXTURES = Path("tests/fixtures/gold_contracts")


def test_load_gold_variant_gene_lookup_contract():
    contract = load_contract("config/gold_contracts/gold_variant_gene_lookup_v1.yaml")

    assert contract.mart == "gold_variant_gene_lookup_v1"
    assert contract.schema == "gold_open"
    assert contract.mandatory == [
        "sample_id", "gene_symbol", "chrom", "pos", "ref", "alt", "tissue",
    ]
    assert contract.good_to_have == ["consequence", "impact", "diagnosis", "filter"]
    assert contract.okay_to_have == [
        "vaf", "hgvsp", "exon", "qc_status", "disease_group",
    ]
    assert contract.not_relevant == [
        "collection_date", "tumor_purity", "notes", "sequencing_platform",
        "library_prep", "patient_id",
    ]


def test_duplicate_column_across_tiers_raises():
    with pytest.raises(ContractError):
        load_contract(str(FIXTURES / "duplicate_column.yaml"))


def test_unknown_tier_name_raises():
    with pytest.raises(ContractError):
        load_contract(str(FIXTURES / "unknown_tier.yaml"))
