from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ib_showcase.analytics import (
    build_filing_event_summary,
    build_filing_reaction_table,
    build_performance_summary,
    build_screening_table,
    build_transformed_macro_snapshot,
)


def test_build_performance_summary_returns_expected_columns() -> None:
    prices = pd.DataFrame(
        {
            "AAA": [100, 102, 104, 106, 108],
            "BBB": [100, 99, 101, 102, 103],
            "^GSPC": [100, 101, 101, 102, 103],
        },
        index=pd.date_range("2024-01-01", periods=5, freq="D"),
    )

    summary = build_performance_summary(prices=prices, benchmark="^GSPC")

    assert "annualized_return_pct" in summary.columns
    assert "annualized_vol_pct" in summary.columns
    assert "beta_vs_benchmark" in summary.columns
    assert len(summary.index) == 3


def test_build_screening_table_creates_scores() -> None:
    performance_summary = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "^GSPC"],
            "total_return_pct": [12.0, 8.0, 10.0],
            "annualized_return_pct": [15.0, 9.0, 11.0],
            "annualized_vol_pct": [20.0, 17.0, 16.0],
            "max_drawdown_pct": [-8.0, -5.0, -6.0],
            "beta_vs_benchmark": [1.1, 0.9, 1.0],
        }
    ).set_index("ticker")

    snapshots = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "company_name": ["Alpha", "Beta"],
            "sector": ["Tech", "Tech"],
            "industry": ["Semis", "Semis"],
            "market_cap": [1000, 1200],
            "current_price": [50, 60],
            "trailing_pe": [20, 25],
            "forward_pe": [18, 23],
            "price_to_book": [3, 4],
            "enterprise_to_revenue": [6, 7],
            "enterprise_to_ebitda": [12, 15],
            "roe_pct": [18, 15],
            "operating_margin_pct": [25, 19],
            "ebitda_margin_pct": [30, 23],
            "revenue_growth_pct": [10, 8],
            "revenue_cagr_3y_pct": [11, 7],
            "debt_to_equity": [40, 60],
            "net_debt_to_ebitda": [1.0, 1.5],
        }
    ).set_index("ticker")

    screening = build_screening_table(
        performance_summary=performance_summary,
        company_snapshots=snapshots,
        benchmark="^GSPC",
    )

    assert "quality_score" in screening.columns
    assert "value_score" in screening.columns
    assert "composite_score" in screening.columns
    assert screening.index[0] == "AAA"


def test_build_transformed_macro_snapshot_formats_cpi_and_rates() -> None:
    macro_data = pd.DataFrame(
        {
            "US 10Y Treasury Yield": [4.0, 4.1, 4.2],
            "US CPI Index": [300.0, 309.0, 318.0],
        },
        index=pd.to_datetime(["2024-01-31", "2024-12-31", "2025-01-31"]),
    )

    snapshot = build_transformed_macro_snapshot(macro_data)

    assert "display_unit" in snapshot.columns
    assert snapshot.loc["US 10Y Treasury Yield", "change_30d"] == pytest.approx(10.0)
    assert snapshot.loc["US CPI Index", "change_1y"] > 0


def test_build_filing_reaction_table_and_summary() -> None:
    price_index = pd.date_range("2024-01-01", periods=10, freq="B")
    prices = pd.DataFrame(
        {
            "AAA": [100, 101, 102, 101, 104, 106, 107, 108, 109, 110],
            "^GSPC": [100, 100.5, 101, 100.8, 101.2, 101.8, 102.0, 102.5, 103.0, 103.4],
        },
        index=price_index,
    )
    volumes = pd.DataFrame(
        {
            "AAA": [10, 10, 10, 10, 20, 22, 21, 19, 18, 17],
            "^GSPC": [1] * 10,
        },
        index=price_index,
    )
    filings = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "form": ["10-Q"],
            "filing_date": [pd.Timestamp("2024-01-05")],
            "acceptance_datetime": [pd.Timestamp("2024-01-05 13:00:00Z")],
            "filing_url": ["https://example.com"],
        }
    )

    reactions = build_filing_reaction_table(
        sec_filings=filings,
        prices=prices,
        volumes=volumes,
        benchmark="^GSPC",
    )
    summary = build_filing_event_summary(reactions)

    assert not reactions.empty
    assert "excess_return_day0_pct" in reactions.columns
    assert summary.index[0] == "10-Q"
