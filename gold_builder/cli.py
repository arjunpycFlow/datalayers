import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

from gold_builder.run import ReconciliationError, SchemaLeakError, run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gold-builder")
    parser.add_argument(
        "--silver-db",
        default="warehouse/silver.duckdb",
        help="path to silver's DuckDB file (default: warehouse/silver.duckdb)",
    )
    parser.add_argument(
        "--out-root",
        default="warehouse",
        help="warehouse root (gold.duckdb written here) (default: warehouse)",
    )
    parser.add_argument(
        "--mart",
        nargs="+",
        default=None,
        help="build only these mart(s) by name — default: build every contract found "
        "in config/gold_contracts/",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not Path(args.silver_db).exists():
        print(f"silver database not found: {args.silver_db}", file=sys.stderr)
        return 1

    run_id = uuid.uuid4().hex
    run_timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    try:
        summary = run(
            silver_db=args.silver_db,
            out_root=args.out_root,
            mart_filter=args.mart,
            run_id=run_id,
            run_timestamp=run_timestamp,
        )
    except (ReconciliationError, SchemaLeakError) as e:
        print(f"reconciliation invariant failed: {e}", file=sys.stderr)
        return 2

    print(summary.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
