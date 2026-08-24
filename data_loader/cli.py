import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

from data_loader.run import ReconciliationError, run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="data-loader")
    parser.add_argument("batch_id", help="e.g. batch_2026_01")
    parser.add_argument(
        "--data-root",
        default="candidate_bundle/data",
        help="landing zone root (default: candidate_bundle/data)",
    )
    parser.add_argument(
        "--out-root",
        default="warehouse",
        help="warehouse root (default: warehouse)",
    )
    return parser


def resolve_batch_dir(data_root: str, batch_id: str) -> Path | None:
    batch_dir = Path(data_root) / batch_id
    if not batch_dir.is_dir():
        return None
    if not any(batch_dir.iterdir()):
        return None
    return batch_dir


def ensure_warehouse_layout(out_root: str) -> None:
    for dataset in ("data", "quarantine"):
        Path(out_root, "bronze", dataset).mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    batch_dir = resolve_batch_dir(args.data_root, args.batch_id)
    if batch_dir is None:
        print(f"batch not found or empty: {args.data_root}/{args.batch_id}", file=sys.stderr)
        return 1

    ensure_warehouse_layout(args.out_root)

    run_id = uuid.uuid4().hex
    run_timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    try:
        summary = run(
            batch_id=args.batch_id,
            data_root=args.data_root,
            out_root=args.out_root,
            run_id=run_id,
            run_timestamp=run_timestamp,
        )
    except ReconciliationError as e:
        print(f"reconciliation invariant failed: {e}", file=sys.stderr)
        return 2

    print(summary.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
