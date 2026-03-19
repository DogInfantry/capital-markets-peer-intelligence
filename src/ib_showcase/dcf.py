from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_number(value: object, default: float | None = None) -> float | None:
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _derive_base_fcf_margin(snapshot_row: pd.Series) -> float:
    latest_revenue = _safe_number(snapshot_row.get("latest_revenue"))
    latest_fcf = _safe_number(snapshot_row.get("latest_free_cash_flow"))
    operating_margin_pct = _safe_number(snapshot_row.get("operating_margin_pct"), 12.0)

    if latest_revenue and latest_fcf is not None:
        return _clip(latest_fcf / latest_revenue, 0.03, 0.35)

    return _clip((operating_margin_pct / 100) * 0.6, 0.05, 0.25)


def _build_growth_path(start_growth: float, terminal_growth: float, years: int = 5) -> list[float]:
    return np.linspace(start_growth, terminal_growth, years).tolist()


def _load_assumptions(assumptions_file: str | None) -> pd.DataFrame:
    if not assumptions_file:
        return pd.DataFrame()
    try:
        assumptions = pd.read_csv(assumptions_file)
    except FileNotFoundError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    if "ticker" not in assumptions.columns:
        return pd.DataFrame()
    assumptions["ticker"] = assumptions["ticker"].astype(str).str.upper()
    return assumptions.set_index("ticker")


def build_dcf_outputs(
    company_snapshots: pd.DataFrame,
    revenue_history: pd.DataFrame,
    macro_snapshot: pd.DataFrame,
    focus_ticker: str | None = None,
    assumptions_file: str | None = None,
    forecast_years: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if company_snapshots.empty:
        empty_summary = pd.DataFrame(
            columns=[
                "company_name",
                "latest_revenue",
                "base_fcf_margin_pct",
                "wacc_pct",
                "terminal_growth_pct",
                "enterprise_value_dcf",
                "equity_value_dcf",
                "implied_share_price",
                "current_price",
                "upside_downside_pct",
            ]
        )
        empty_projection = pd.DataFrame(
            columns=["ticker", "year", "projected_revenue", "projected_fcf", "discount_factor", "present_value_fcf"]
        )
        empty_sensitivity = pd.DataFrame()
        return empty_summary, empty_projection, empty_sensitivity

    risk_free = 0.045
    inflation_anchor = 0.025
    high_yield_spread = 0.04

    if not macro_snapshot.empty:
        risk_free = _safe_number(macro_snapshot.loc["US 10Y Treasury Yield", "latest"], 4.5) / 100 if "US 10Y Treasury Yield" in macro_snapshot.index else risk_free
        inflation_anchor = _safe_number(macro_snapshot.loc["US CPI Index", "change_1y"], 2.5) / 100 if "US CPI Index" in macro_snapshot.index else inflation_anchor
        high_yield_spread = _safe_number(macro_snapshot.loc["High Yield Spread", "latest"], 4.0) / 100 if "High Yield Spread" in macro_snapshot.index else high_yield_spread

    terminal_growth = _clip(max(0.02, min(0.035, inflation_anchor if inflation_anchor > 0 else 0.025)), 0.02, 0.035)
    assumptions = _load_assumptions(str(assumptions_file) if assumptions_file else None)

    summary_rows: list[dict[str, float | str | None]] = []
    projection_rows: list[dict[str, float | str | None]] = []

    for ticker, row in company_snapshots.iterrows():
        latest_revenue = _safe_number(row.get("latest_revenue"))
        if latest_revenue is None:
            ticker_revenue_history = revenue_history.loc[revenue_history["ticker"] == ticker, "revenue"]
            if not ticker_revenue_history.empty:
                latest_revenue = _safe_number(ticker_revenue_history.iloc[-1])

        if latest_revenue is None:
            continue

        market_cap = _safe_number(row.get("market_cap"), 0.0) or 0.0
        total_debt = _safe_number(row.get("latest_total_debt"), 0.0) or 0.0
        cash = _safe_number(row.get("latest_cash"), 0.0) or 0.0
        shares_outstanding = _safe_number(row.get("shares_outstanding"))
        current_price = _safe_number(row.get("current_price"))
        beta = _clip(_safe_number(row.get("beta"), 1.0) or 1.0, 0.6, 2.0)
        revenue_cagr_pct = _safe_number(row.get("revenue_cagr_3y_pct"), 8.0) or 8.0

        normalized_start_growth = _clip(revenue_cagr_pct / 100, 0.03, 0.16)
        base_fcf_margin = _derive_base_fcf_margin(row)
        target_fcf_margin = _clip(max(base_fcf_margin, 0.12), 0.08, 0.28)

        equity_weight = market_cap / (market_cap + total_debt) if (market_cap + total_debt) > 0 else 0.8
        debt_weight = 1 - equity_weight
        cost_of_equity = risk_free + beta * 0.055
        cost_of_debt = risk_free + high_yield_spread
        wacc = _clip(equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - 0.25), 0.07, 0.14)
        terminal_growth_for_ticker = min(terminal_growth, wacc - 0.01)

        if ticker in assumptions.index:
            manual = assumptions.loc[ticker]
            normalized_start_growth = _clip(
                (_safe_number(manual.get("revenue_growth_start_pct"), normalized_start_growth * 100) or normalized_start_growth * 100) / 100,
                0.01,
                0.20,
            )
            target_fcf_margin = _clip(
                (_safe_number(manual.get("target_fcf_margin_pct"), target_fcf_margin * 100) or target_fcf_margin * 100) / 100,
                0.03,
                0.35,
            )
            wacc = _clip(
                (_safe_number(manual.get("wacc_pct"), wacc * 100) or wacc * 100) / 100,
                0.06,
                0.16,
            )
            terminal_growth_for_ticker = min(
                (_safe_number(manual.get("terminal_growth_pct"), terminal_growth_for_ticker * 100) or terminal_growth_for_ticker * 100) / 100,
                wacc - 0.01,
            )

        growth_path = _build_growth_path(normalized_start_growth, terminal_growth_for_ticker, years=forecast_years)
        margin_path = np.linspace(base_fcf_margin, target_fcf_margin, forecast_years).tolist()

        projected_revenue = latest_revenue
        pv_fcf_total = 0.0
        terminal_value = 0.0

        for year_number, (growth_rate, fcf_margin) in enumerate(zip(growth_path, margin_path), start=1):
            projected_revenue *= 1 + growth_rate
            projected_fcf = projected_revenue * fcf_margin
            discount_factor = (1 + wacc) ** year_number
            pv_fcf = projected_fcf / discount_factor
            pv_fcf_total += pv_fcf

            if year_number == forecast_years:
                terminal_value = projected_fcf * (1 + terminal_growth_for_ticker) / (wacc - terminal_growth_for_ticker)

            projection_rows.append(
                {
                    "ticker": ticker,
                    "year": year_number,
                    "projected_revenue": projected_revenue,
                    "projected_fcf": projected_fcf,
                    "fcf_margin_pct": fcf_margin * 100,
                    "revenue_growth_pct": growth_rate * 100,
                    "discount_factor": discount_factor,
                    "present_value_fcf": pv_fcf,
                }
            )

        pv_terminal_value = terminal_value / ((1 + wacc) ** forecast_years)
        enterprise_value_dcf = pv_fcf_total + pv_terminal_value
        equity_value_dcf = enterprise_value_dcf - total_debt + cash

        if shares_outstanding is None and current_price not in (None, 0) and market_cap > 0:
            shares_outstanding = market_cap / current_price

        implied_share_price = equity_value_dcf / shares_outstanding if shares_outstanding not in (None, 0) else np.nan
        upside_downside_pct = (
            ((implied_share_price / current_price) - 1) * 100
            if current_price not in (None, 0) and not pd.isna(implied_share_price)
            else np.nan
        )

        summary_rows.append(
            {
                "ticker": ticker,
                "company_name": row.get("company_name"),
                "latest_revenue": latest_revenue,
                "base_fcf_margin_pct": base_fcf_margin * 100,
                "wacc_pct": wacc * 100,
                "terminal_growth_pct": terminal_growth_for_ticker * 100,
                "enterprise_value_dcf": enterprise_value_dcf,
                "equity_value_dcf": equity_value_dcf,
                "implied_share_price": implied_share_price,
                "current_price": current_price,
                "upside_downside_pct": upside_downside_pct,
            }
        )

    dcf_summary = pd.DataFrame(summary_rows).set_index("ticker") if summary_rows else pd.DataFrame()
    dcf_projection = pd.DataFrame(projection_rows)

    if dcf_summary.empty:
        return dcf_summary, dcf_projection, pd.DataFrame()

    dcf_summary = dcf_summary.sort_values("upside_downside_pct", ascending=False)
    selected_ticker = focus_ticker if focus_ticker in dcf_summary.index else dcf_summary.index[0]
    base_case = dcf_summary.loc[selected_ticker]
    selected_projection = dcf_projection[dcf_projection["ticker"] == selected_ticker].copy()
    final_projected_fcf = _safe_number(selected_projection["projected_fcf"].iloc[-1], 0.0) or 0.0
    total_debt = _safe_number(company_snapshots.loc[selected_ticker].get("latest_total_debt"), 0.0) or 0.0
    cash = _safe_number(company_snapshots.loc[selected_ticker].get("latest_cash"), 0.0) or 0.0
    shares_outstanding = _safe_number(company_snapshots.loc[selected_ticker].get("shares_outstanding"))
    current_price = _safe_number(company_snapshots.loc[selected_ticker].get("current_price"))
    market_cap = _safe_number(company_snapshots.loc[selected_ticker].get("market_cap"), 0.0) or 0.0
    if shares_outstanding is None and current_price not in (None, 0) and market_cap > 0:
        shares_outstanding = market_cap / current_price

    wacc_values = [max(base_case["wacc_pct"] - 1.0, 6.0), base_case["wacc_pct"], base_case["wacc_pct"] + 1.0]
    growth_values = [
        max(base_case["terminal_growth_pct"] - 0.5, 1.5),
        base_case["terminal_growth_pct"],
        min(base_case["terminal_growth_pct"] + 0.5, min(base_case["wacc_pct"] - 1.0, 4.0)),
    ]

    sensitivity_rows: list[dict[str, float | str]] = []
    for terminal_growth_pct in growth_values:
        for wacc_pct in wacc_values:
            wacc = wacc_pct / 100
            terminal_growth_rate = terminal_growth_pct / 100
            if wacc <= terminal_growth_rate:
                continue
            terminal_value = final_projected_fcf * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate)
            pv_terminal = terminal_value / ((1 + wacc) ** forecast_years)
            enterprise_value = selected_projection["present_value_fcf"].sum() + pv_terminal
            equity_value = enterprise_value - total_debt + cash
            implied_share_price = (
                equity_value / shares_outstanding if shares_outstanding not in (None, 0) else np.nan
            )
            sensitivity_rows.append(
                {
                    "ticker": selected_ticker,
                    "terminal_growth_pct": terminal_growth_pct,
                    "wacc_pct": wacc_pct,
                    "implied_share_price": implied_share_price,
                }
            )

    dcf_sensitivity = pd.DataFrame(sensitivity_rows)
    return dcf_summary, dcf_projection, dcf_sensitivity
