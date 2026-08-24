import csv
from collections import defaultdict
from dataclasses import dataclass, fields
from pathlib import Path

from data_loader.models import QuarantineRow

_KNOWN_COLUMNS = [
    "sample_id",
    "patient_id",
    "batch_id",
    "collection_date",
    "tissue",
    "diagnosis",
    "disease_group",
    "tumor_purity",
    "sex_reported",
    "sex_inferred",
    "sequencing_platform",
    "qc_status",
    "notes",
    "library_prep",
]


@dataclass
class ManifestStats:
    lines_read: int = 0
    duplicates_collapsed: int = 0


@dataclass
class ParsedManifestRow:
    sample_id: str
    patient_id: str | None = None
    batch_id: str | None = None
    collection_date: str | None = None
    tissue: str | None = None
    diagnosis: str | None = None
    disease_group: str | None = None
    tumor_purity: str | None = None
    sex_reported: str | None = None
    sex_inferred: str | None = None
    sequencing_platform: str | None = None
    qc_status: str | None = None
    notes: str | None = None
    library_prep: str | None = None
    source_file: str = ""
    source_line_no: int = 0


_ROW_FIELDS = {f.name for f in fields(ParsedManifestRow)} - {"source_file", "source_line_no"}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _row_to_raw_text(row: dict[str, str]) -> str:
    return ",".join(f"{k}={v}" for k, v in row.items())


def parse_manifest(
    path: Path,
    batch_id: str,
    run_id: str = "",
    run_timestamp: str = "",
) -> tuple[list[ParsedManifestRow], list[QuarantineRow], ManifestStats]:
    quarantine: list[QuarantineRow] = []
    by_sample: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    stats = ManifestStats()

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        expected_field_count = len(header)

        for line_no, raw_fields in enumerate(reader, start=2):
            stats.lines_read += 1
            if len(raw_fields) != expected_field_count:
                quarantine.append(
                    QuarantineRow(
                        batch_id=batch_id,
                        entity_type="manifest_row",
                        source_file=str(path),
                        source_line_no=str(line_no),
                        raw_text=",".join(raw_fields),
                        reason_code="MALFORMED_MANIFEST_ROW",
                        reason_detail=(
                            f"expected {expected_field_count} columns, got {len(raw_fields)}"
                        ),
                        run_id=run_id,
                        run_timestamp=run_timestamp,
                    )
                )
                continue

            row = dict(zip(header, raw_fields))
            sample_id = _clean(row.get("sample_id"))
            if sample_id is None:
                quarantine.append(
                    QuarantineRow(
                        batch_id=batch_id,
                        entity_type="manifest_row",
                        source_file=str(path),
                        source_line_no=str(line_no),
                        raw_text=_row_to_raw_text(row),
                        reason_code="MALFORMED_MANIFEST_ROW",
                        reason_detail="sample_id is empty",
                        run_id=run_id,
                        run_timestamp=run_timestamp,
                    )
                )
                continue

            by_sample[sample_id].append((line_no, row))

    rows: list[ParsedManifestRow] = []

    for sample_id, entries in by_sample.items():
        cleaned = [
            {k: _clean(v) for k, v in row.items() if k in _ROW_FIELDS or k == "sample_id"}
            for _, row in entries
        ]

        if len(entries) == 1 or all(c == cleaned[0] for c in cleaned):
            line_no, raw_row = entries[0]
            stats.duplicates_collapsed += len(entries) - 1
            rows.append(
                ParsedManifestRow(
                    **cleaned[0],
                    source_file=str(path),
                    source_line_no=line_no,
                )
            )
            continue

        # Duplicate sample_id with disagreeing field values — unresolvable.
        disagreeing = sorted(
            k
            for k in cleaned[0]
            if k != "sample_id" and len({c[k] for c in cleaned}) > 1
        )
        detail = "; ".join(
            f"{k} disagrees: " + " vs ".join(repr(c[k]) for c in cleaned)
            for k in disagreeing
        )
        for line_no, raw_row in entries:
            quarantine.append(
                QuarantineRow(
                    batch_id=batch_id,
                    entity_type="manifest_conflicting_duplicate",
                    source_file=str(path),
                    source_line_no=str(line_no),
                    raw_text=_row_to_raw_text(raw_row),
                    reason_code="CONFLICTING_DUPLICATE",
                    reason_detail=detail,
                    run_id=run_id,
                    run_timestamp=run_timestamp,
                )
            )

    return rows, quarantine, stats
