import re
from dataclasses import dataclass, field
from pathlib import Path

_HEADER_LINE = re.compile(r"^##(?P<key>INFO|FORMAT|FILTER)=<(?P<body>.*)>$")
_CSQ_FORMAT_CLAUSE = re.compile(r"Format:\s*([A-Za-z0-9_|]+)")


@dataclass
class HeaderDeclaration:
    id: str
    number: str | None
    type: str | None
    description: str | None


@dataclass
class VcfContract:
    """Per-file VCF header contract: what a file declares about itself."""

    info: dict[str, HeaderDeclaration] = field(default_factory=dict)
    format: dict[str, HeaderDeclaration] = field(default_factory=dict)
    filter: dict[str, HeaderDeclaration] = field(default_factory=dict)
    csq_field_order: list[str] = field(default_factory=list)
    sample_columns: list[str] = field(default_factory=list)


def _split_kv_body(body: str) -> dict[str, str]:
    """Split a `##KEY=<A=..,B=..,Description="...">` body into a dict, respecting
    commas inside the quoted Description value."""
    parts: dict[str, str] = {}
    depth_quote = False
    current = []
    tokens: list[str] = []
    for ch in body:
        if ch == '"':
            depth_quote = not depth_quote
            current.append(ch)
        elif ch == "," and not depth_quote:
            tokens.append("".join(current))
            current = []
        else:
            current.append(ch)
    tokens.append("".join(current))

    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parts[key.strip()] = value.strip().strip('"')
    return parts


def parse_vcf_headers(path: Path) -> VcfContract:
    contract = VcfContract()

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            if line.startswith("#CHROM"):
                columns = line.split("\t")
                contract.sample_columns = columns[9:]
                break

            match = _HEADER_LINE.match(line)
            if not match:
                continue

            kv = _split_kv_body(match.group("body"))
            decl = HeaderDeclaration(
                id=kv.get("ID", ""),
                number=kv.get("Number"),
                type=kv.get("Type"),
                description=kv.get("Description"),
            )

            section = match.group("key")
            if section == "INFO":
                contract.info[decl.id] = decl
                if decl.id == "CSQ" and decl.description:
                    fmt_match = _CSQ_FORMAT_CLAUSE.search(decl.description)
                    if fmt_match:
                        contract.csq_field_order = fmt_match.group(1).split("|")
            elif section == "FORMAT":
                contract.format[decl.id] = decl
            elif section == "FILTER":
                contract.filter[decl.id] = decl

    return contract
