from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ib_showcase.config import ProjectConfig  # noqa: E402
from ib_showcase.pipeline import run_analysis_pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an investment-banking style market, valuation, and DCF dashboard."
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["GS", "MS", "JPM", "BAC", "C"],
        help="Peer set tickers to analyze.",
    )
    parser.add_argument(
        "--benchmark",
        default="^GSPC",
        help="Benchmark ticker for beta and relative performance.",
    )
    parser.add_argument(
        "--start",
        default="2021-01-01",
        help="Analysis start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Optional end date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--sector-label",
        default="Investment Banking Peer Set",
        help="Friendly name used in titles and reports.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory for charts, tables, workbook, and reports.",
    )
    parser.add_argument(
        "--assumptions-file",
        default=None,
        help="Optional CSV file with manual DCF assumptions overrides.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ProjectConfig(
        tickers=args.tickers,
        benchmark=args.benchmark,
        start=args.start,
        end=args.end,
        sector_label=args.sector_label,
        output_dir=Path(args.output_dir),
        assumptions_file=Path(args.assumptions_file) if args.assumptions_file else None,
    )

    results = run_analysis_pipeline(config=config, write_outputs=True)
    output_dirs = results["output_dirs"]
    print("Analysis complete.")
    print(f"Outputs saved to: {output_dirs['base']}")


if __name__ == "__main__":
    main()
