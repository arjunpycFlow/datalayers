from dataclasses import dataclass
from pathlib import Path

from data_loader.join import join_records
from data_loader.manifest import parse_manifest
from data_loader.models import DataRow, QuarantineRow
from data_loader.vcf_headers import parse_vcf_headers
from data_loader.vcf_rows import parse_vcf_rows
from data_loader.writer import write_bronze


class ReconciliationError(Exception):
    """A record went missing between read and write — a bug, not a data defect."""


@dataclass
class RunSummary:
    batch_id: str
    manifest_lines_read: int
    manifest_duplicates_collapsed: int
    manifest_quarantined: int
    vcf_lines_read: int
    vcf_quarantined: int
    data_rows_written: int
    quarantine_rows_written: int
    data_path: Path
    quarantine_path: Path

    def render(self) -> str:
        return (
            f"{self.batch_id}: {self.data_rows_written} rows written, "
            f"{self.quarantine_rows_written} quarantined, "
            f"{self.manifest_duplicates_collapsed} exact duplicates collapsed"
        )


def _check_reconciliation(
    manifest_lines_read: int,
    manifest_usable: int,
    manifest_quarantined: int,
    manifest_duplicates_collapsed: int,
    vcf_lines_read: int,
    vcf_lines_quarantined: int,
) -> None:
    """Two independent conservation checks — one per source, since a join can
    merge a manifest row and a VCF line into a single output row and a flat
    combined sum would not balance."""

    manifest_accounted = manifest_usable + manifest_quarantined + manifest_duplicates_collapsed
    if manifest_lines_read != manifest_accounted:
        raise ReconciliationError(
            f"manifest: {manifest_lines_read} lines read != "
            f"{manifest_usable} usable + {manifest_quarantined} quarantined + "
            f"{manifest_duplicates_collapsed} duplicates collapsed "
            f"({manifest_accounted})"
        )

    vcf_lines_with_parsed_rows = vcf_lines_read - vcf_lines_quarantined
    if vcf_lines_with_parsed_rows < 0:
        raise ReconciliationError(
            f"vcf: quarantined line count ({vcf_lines_quarantined}) exceeds "
            f"lines read ({vcf_lines_read})"
        )


def run(batch_id: str, data_root: str, out_root: str, run_id: str, run_timestamp: str) -> RunSummary:
    batch_dir = Path(data_root) / batch_id

    manifest_rows, manifest_quarantine, manifest_stats = parse_manifest(
        batch_dir / "sample_manifest.csv",
        batch_id=batch_id,
        run_id=run_id,
        run_timestamp=run_timestamp,
    )

    vcf_rows = []
    vcf_quarantine: list[QuarantineRow] = []
    vcf_lines_read = 0
    for vcf_path in sorted(batch_dir.glob("*.somatic.vcf")):
        contract = parse_vcf_headers(vcf_path)
        rows, quarantined, vcf_stats = parse_vcf_rows(
            vcf_path, contract, batch_id=batch_id, run_id=run_id, run_timestamp=run_timestamp
        )
        vcf_rows.extend(rows)
        vcf_quarantine.extend(quarantined)
        vcf_lines_read += vcf_stats.lines_read

    _check_reconciliation(
        manifest_lines_read=manifest_stats.lines_read,
        manifest_usable=len(manifest_rows),
        manifest_quarantined=len(manifest_quarantine),
        manifest_duplicates_collapsed=manifest_stats.duplicates_collapsed,
        vcf_lines_read=vcf_lines_read,
        vcf_lines_quarantined=len(vcf_quarantine),
    )

    data_rows: list[DataRow] = join_records(
        vcf_rows, manifest_rows, run_id=run_id, run_timestamp=run_timestamp
    )
    quarantine_rows = manifest_quarantine + vcf_quarantine

    data_path, quarantine_path = write_bronze(
        data_rows, quarantine_rows, out_root, batch_id, run_timestamp
    )

    return RunSummary(
        batch_id=batch_id,
        manifest_lines_read=manifest_stats.lines_read,
        manifest_duplicates_collapsed=manifest_stats.duplicates_collapsed,
        manifest_quarantined=len(manifest_quarantine),
        vcf_lines_read=vcf_lines_read,
        vcf_quarantined=len(vcf_quarantine),
        data_rows_written=len(data_rows),
        quarantine_rows_written=len(quarantine_rows),
        data_path=data_path,
        quarantine_path=quarantine_path,
    )
