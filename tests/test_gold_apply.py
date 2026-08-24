import duckdb

from gold_builder.apply import apply_contract
from gold_builder.contracts import load_contract
from gold_builder.marts import variant_gene_lookup

CONTRACT = load_contract("config/gold_contracts/gold_variant_gene_lookup_v1.yaml")


def _row(**overrides):
    row = {
        "sample_id": "S-9001",
        "gene_symbol": "TP53",
        "chrom": "chr17",
        "pos": "7675088",
        "ref": "C",
        "alt": "T",
        "tissue": "Lung",
        "consequence": "missense_variant",
        "impact": "MODERATE",
        "diagnosis": "Lung adenocarcinoma",
        "filter": "PASS",
        "vaf": 0.35,
        "hgvsp": None,
        "exon": "5/11",
        "qc_status": "PASS",
        "disease_group": "Thoracic",
        "collection_date": "2026-01-05",
        "tumor_purity": 0.32,
        "notes": "FFPE block",
        "sequencing_platform": "NovaSeq X",
        "library_prep": None,
        "patient_id": "P-9001",
    }
    row.update(overrides)
    return row


def test_missing_mandatory_column_quarantines_with_correct_list():
    output, quarantine = apply_contract(
        CONTRACT, _row(tissue=None), row_identifier="S-9001", run_id="t", run_timestamp="t"
    )
    assert output is None
    assert quarantine is not None
    assert quarantine.exclusion_reason_code == "MISSING_MANDATORY_COLUMN"
    assert quarantine.missing_columns == ["tissue"]


def test_missing_good_to_have_column_still_lands():
    output, quarantine = apply_contract(
        CONTRACT, _row(diagnosis=None), row_identifier="S-9001", run_id="t", run_timestamp="t"
    )
    assert quarantine is None
    assert output is not None
    assert output["diagnosis"] is None
    assert output["sample_id"] == "S-9001"


def test_not_relevant_columns_absent_from_output_shape():
    output, _ = apply_contract(
        CONTRACT, _row(), row_identifier="S-9001", run_id="t", run_timestamp="t"
    )
    assert "collection_date" not in output
    assert "tumor_purity" not in output
    assert "patient_id" not in output
    assert "notes" not in output


def test_s0011_quarantines_for_this_mart_specifically_against_real_data():
    con = duckdb.connect("warehouse/silver.duckdb")
    rows = con.execute(
        """
        SELECT s.sample_id, v.chrom, v.pos, v.ref, v.alt, v.gene_symbol, s.tissue,
               v.consequence, v.impact, s.diagnosis, v.filter, v.vaf, v.hgvsp, v.exon,
               s.qc_status, s.disease_group, s.collection_date, s.tumor_purity,
               s.notes, s.sequencing_platform, s.library_prep, s.patient_id
        FROM variant_calls v JOIN samples s USING (sample_id)
        WHERE s.sample_id = 'S-0011'
        """
    ).fetchall()
    cols = [d[0] for d in con.description]
    assert rows, "expected S-0011 to have variant rows in real silver output"

    outputs = []
    quarantines = []
    for r in rows:
        row = dict(zip(cols, r))
        output, quarantine = apply_contract(
            CONTRACT, row, row_identifier=row["sample_id"], run_id="t", run_timestamp="t"
        )
        outputs.append(output)
        quarantines.append(quarantine)

    assert all(o is None for o in outputs)
    assert all(q is not None for q in quarantines)
    assert all(q.exclusion_reason_code == "MISSING_MANDATORY_COLUMN" for q in quarantines)
    assert all("tissue" in q.missing_columns for q in quarantines)


def test_build_mart_end_to_end_against_real_silver_output():
    con = duckdb.connect("warehouse/silver.duckdb")
    rows, quarantine = variant_gene_lookup.build(
        con, CONTRACT, run_id="test-run", run_timestamp="20260101T000000"
    )

    assert len(rows) > 0
    assert len(quarantine) > 0  # S-0011's rows, at minimum

    n_variant_calls = con.execute("SELECT COUNT(*) FROM variant_calls").fetchone()[0]
    assert len(rows) + len(quarantine) == n_variant_calls

    tp53_rows = [r for r in rows if r["gene_symbol"] == "TP53"]
    assert tp53_rows
    for r in tp53_rows:
        assert set(r.keys()) == set(CONTRACT.present_columns)
        assert "collection_date" not in r  # not_relevant, verified absent

    s0011_quarantined = [q for q in quarantine if "sample_id=S-0011" in q.row_identifier]
    assert len(s0011_quarantined) == 57  # all of S-0011's variant rows (confirmed count)
