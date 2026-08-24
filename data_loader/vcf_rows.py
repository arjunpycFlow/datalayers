from dataclasses import dataclass, field
from pathlib import Path

from data_loader.models import QuarantineRow
from data_loader.vcf_headers import VcfContract


@dataclass
class VcfRowStats:
    lines_read: int = 0


@dataclass
class ParsedVcfRow:
    """One (sample, variant) row parsed from a VCF data line."""

    sample_id: str
    chrom: str
    pos: str
    id: str | None
    ref: str
    alt: str
    qual: str | None
    filter: str | None
    info: dict[str, str] = field(default_factory=dict)
    format_keys: list[str] = field(default_factory=list)
    genotype_values: list[str] = field(default_factory=list)
    source_file: str = ""
    source_line_no: int = 0
    pipeline_version: str | None = None


def _null(value: str) -> str | None:
    """VCF's missing-value sentinel `.` and empty string both become NULL."""
    return None if value in (".", "") else value


def _parse_info(raw: str, csq_field_order: list[str]) -> dict[str, str]:
    info: dict[str, str] = {}
    if not raw or raw == ".":
        return info
    for part in raw.split(";"):
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            if key == "CSQ" and csq_field_order:
                sub_values = value.split("|")
                for name, sub_value in zip(csq_field_order, sub_values):
                    if sub_value:
                        info[f"CSQ_{name}"] = sub_value
            else:
                info[key] = value
        else:
            # Bare key, no `=value` — a Flag-type INFO field (e.g. HOTSPOT).
            info[part] = "true"
    return info


def parse_vcf_rows(
    path: Path,
    contract: VcfContract,
    batch_id: str = "",
    run_id: str = "",
    run_timestamp: str = "",
) -> tuple[list[ParsedVcfRow], list[QuarantineRow], VcfRowStats]:
    rows: list[ParsedVcfRow] = []
    quarantine: list[QuarantineRow] = []
    stats = VcfRowStats()

    n_samples = len(contract.sample_columns)
    expected_field_count = 9 + n_samples

    pipeline_version = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("##source="):
            pipeline_version = line.split("=", 1)[1]
            break
        if line.startswith("#CHROM"):
            break

    with open(path, encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n")

            if not line or line.startswith("#"):
                continue

            stats.lines_read += 1
            fields = line.split("\t")
            if len(fields) != expected_field_count:
                quarantine.append(
                    QuarantineRow(
                        batch_id=batch_id,
                        entity_type="vcf_row",
                        source_file=str(path),
                        source_line_no=str(line_no),
                        raw_text=line,
                        reason_code="MALFORMED_VCF_LINE",
                        reason_detail=(
                            f"expected {expected_field_count} tab-separated fields, "
                            f"got {len(fields)}"
                        ),
                        run_id=run_id,
                        run_timestamp=run_timestamp,
                    )
                )
                continue

            chrom, pos, vid, ref, alt, qual, filt, info_raw, format_raw, *genotype_raws = fields
            info = _parse_info(info_raw, contract.csq_field_order)
            format_keys = format_raw.split(":")

            for sample_id, genotype_raw in zip(contract.sample_columns, genotype_raws):
                rows.append(
                    ParsedVcfRow(
                        sample_id=sample_id,
                        chrom=chrom,
                        pos=pos,
                        id=_null(vid),
                        ref=ref,
                        alt=alt,
                        qual=_null(qual),
                        filter=_null(filt),
                        info=info,
                        format_keys=format_keys,
                        genotype_values=genotype_raw.split(":"),
                        source_file=str(path),
                        source_line_no=line_no,
                        pipeline_version=pipeline_version,
                    )
                )

    return rows, quarantine, stats
