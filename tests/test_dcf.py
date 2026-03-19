from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ib_showcase.dcf import build_dcf_outputs


def test_build_dcf_outputs_creates_summary_and_projection() -> None:
    company_snapshots = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "company_name": ["Alpha Co"],
            "latest_revenue": [1000.0],
            "latest_free_cash_flow": [120.0],
            "latest_total_debt": [100.0],
            "latest_cash": [80.0],
            "market_cap": [2000.0],
            "current_price": [20.0],
            "shares_outstanding": [100.0],
            "beta": [1.1],
            "revenue_cagr_3y_pct": [8.0],
            "operating_margin_pct": [20.0],
        }
    ).set_index("ticker")

    revenue_history = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA", "AAA"],
            "year": [2021, 2022, 2023],
            "revenue": [850.0, 920.0, 1000.0],
        }
    )

    macro_snapshot = pd.DataFrame(
        {
            "series": ["US 10Y Treasury Yield", "US CPI Index", "High Yield Spread"],
            "latest": [4.2, 320.0, 3.5],
            "change_30d": [0.1, 2.0, -0.2],
            "change_1y": [0.4, 8.0, 0.3],
        }
    ).set_index("series")

    dcf_summary, dcf_projection, dcf_sensitivity = build_dcf_outputs(
        company_snapshots=company_snapshots,
        revenue_history=revenue_history,
        macro_snapshot=macro_snapshot,
        focus_ticker="AAA",
    )

    assert not dcf_summary.empty
    assert not dcf_projection.empty
    assert not dcf_sensitivity.empty
    assert "implied_share_price" in dcf_summary.columns
    assert dcf_projection["ticker"].iloc[0] == "AAA"
