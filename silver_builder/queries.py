"""The brief's two required example query shapes, run directly against
warehouse/silver.duckdb — proof the schema actually answers them, not just a
nice-to-have."""

VARIANTS_IN_GENE_WITH_SAMPLE_TISSUE = """
    SELECT
        v.sample_id,
        v.gene_symbol,
        v.consequence,
        v.impact,
        s.tissue,
        s.diagnosis
    FROM variant_calls v
    JOIN samples s ON s.sample_id = v.sample_id
    WHERE v.gene_symbol = ?
    ORDER BY v.sample_id
"""

VARIANT_COUNT_PER_GENE_WITH_DISTINCT_PATIENTS = """
    SELECT
        v.gene_symbol,
        COUNT(*) AS n_variants,
        COUNT(DISTINCT s.patient_id) AS n_distinct_patients
    FROM variant_calls v
    JOIN samples s ON s.sample_id = v.sample_id
    WHERE v.gene_symbol IS NOT NULL
    GROUP BY v.gene_symbol
    ORDER BY n_variants DESC
"""
