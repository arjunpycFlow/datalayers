import argparse
import sys
import uuid
from datetime import datetime

from silver_builder.run import ReconciliationError, run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="silver-builder")
    parser.add_argument(
        "--bronze-data-root",
        default="warehouse/bronze/data",
        help="root to auto-discover bronze data files under (default: warehouse/bronze/data)",
    )
    parser.add_argument(
        "--bronze-quarantine-root",
        default="warehouse/bronze/quarantine",
        help="root to auto-discover bronze quarantine files under, for audit counts only "
        "(default: warehouse/bronze/quarantine)",
    )
    parser.add_argument(
        "--data-files",
        nargs="+",
        default=None,
        help="explicit bronze data_*.parquet paths — overrides auto-discovery entirely",
    )
    parser.add_argument(
        "--out-root",
        default="warehouse",
        help="warehouse root (silver.duckdb written here) (default: warehouse)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    run_id = uuid.uuid4().hex
    run_timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    try:
        summary = run(
            bronze_data_root=args.bronze_data_root,
            explicit_data_files=args.data_files,
            out_root=args.out_root,
            run_id=run_id,
            run_timestamp=run_timestamp,
        )
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    except ReconciliationError as e:
        print(f"reconciliation invariant failed: {e}", file=sys.stderr)
        return 2

    print(summary.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
