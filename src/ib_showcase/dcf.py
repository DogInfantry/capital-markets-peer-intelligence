from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_SCENARIO_PRESETS: dict[str, dict[str, dict[str, float]]] = {
    "default": {
        "Bear": {"growth_delta_pct": -2.0, "margin_delta_pct": -1.5, "wacc_delta_pct": 1.0, "terminal_growth_delta_pct": -0.5},
        "Base": {"growth_delta_pct": 0.0, "margin_delta_pct": 0.0, "wacc_delta_pct": 0.0, "terminal_growth_delta_pct": 0.0},
        "Bull": {"growth_delta_pct": 2.0, "margin_delta_pct": 1.5, "wacc_delta_pct": -1.0, "terminal_growth_delta_pct": 0.5},
    },
    "financial services": {
        "Bear": {"growth_delta_pct": -1.5, "margin_delta_pct": -1.0, "wacc_delta_pct": 0.8, "terminal_growth_delta_pct": -0.4},
        "Base": {"growth_delta_pct": 0.0, "margin_delta_pct": 0.0, "wacc_delta_pct": 0.0, "terminal_growth_delta_pct": 0.0},
        "Bull": {"growth_delta_pct": 1.5, "margin_delta_pct": 1.0, "wacc_delta_pct": -0.8, "terminal_growth_delta_pct": 0.4},
    },
    "technology": {
        "Bear": {"growth_delta_pct": -3.0, "margin_delta_pct": -2.0, "wacc_delta_pct": 1.2, "terminal_growth_delta_pct": -0.6},
        "Base": {"growth_delta_pct": 0.0, "margin_delta_pct": 0.0, "wacc_delta_pct": 0.0, "terminal_growth_delta_pct": 0.0},
        "Bull": {"growth_delta_pct": 3.0, "margin_delta_pct": 2.0, "wacc_delta_pct": -1.2, "terminal_growth_delta_pct": 0.6},
    },
    "healthcare": {
        "Bear": {"growth_delta_pct": -2.0, "margin_delta_pct": -1.0, "wacc_delta_pct": 0.8, "terminal_growth_delta_pct": -0.4},
        "Base": {"growth_delta_pct": 0.0, "margin_delta_pct": 0.0, "wacc_delta_pct": 0.0, "terminal_growth_delta_pct": 0.0},
        "Bull": {"growth_delta_pct": 2.0, "margin_delta_pct": 1.0, "wacc_delta_pct": -0.8, "terminal_growth_delta_pct": 0.4},
    },
    "industrials": {
        "Bear": {"growth_delta_pct": -2.5, "margin_delta_pct": -1.5, "wacc_delta_pct": 1.0, "terminal_growth_delta_pct": -0.5},
        "Base": {"growth_delta_pct": 0.0, "margin_delta_pct": 0.0, "wacc_delta_pct": 0.0, "terminal_growth_delta_pct": 0.0},
        "Bull": {"growth_delta_pct": 2.5, "margin_delta_pct": 1.5, "wacc_delta_pct": -1.0, "terminal_growth_delta_pct": 0.5},
    },
}


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


def _resolve_sector_key(row: pd.Series) -> str:
    sector = str(row.get("sector") or "").strip().lower()
    if sector in DEFAULT_SCENARIO_PRESETS:
        return sector
    return "default"


def _derive_base_assumptions(
    row: pd.Series,
    latest_revenue: float,
    risk_free: float,
    high_yield_spread: float,
    terminal_growth: float,
    assumptions: pd.DataFrame,
) -> dict[str, float]:
    market_cap = _safe_number(row.get("market_cap"), 0.0) or 0.0
    total_debt = _safe_number(row.get("latest_total_debt"), 0.0) or 0.0
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

    ticker = row.name
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

    return {
        "latest_revenue": latest_revenue,
        "base_growth_start": normalized_start_growth,
        "base_fcf_margin": base_fcf_margin,
        "target_fcf_margin": target_fcf_margin,
        "wacc": wacc,
        "terminal_growth": terminal_growth_for_ticker,
    }


def _run_dcf_case(
    row: pd.Series,
    assumptions: dict[str, float],
    case_name: str,
    forecast_years: int,
) -> tuple[dict[str, float | str | None], list[dict[str, float | str | None]]]:
    latest_revenue = assumptions["latest_revenue"]
    start_growth = assumptions["base_growth_start"]
    base_fcf_margin = assumptions["base_fcf_margin"]
    target_fcf_margin = assumptions["target_fcf_margin"]
    wacc = assumptions["wacc"]
    terminal_growth = assumptions["terminal_growth"]

    total_debt = _safe_number(row.get("latest_total_debt"), 0.0) or 0.0
    cash = _safe_number(row.get("latest_cash"), 0.0) or 0.0
    market_cap = _safe_number(row.get("market_cap"), 0.0) or 0.0
    current_price = _safe_number(row.get("current_price"))
    shares_outstanding = _safe_number(row.get("shares_outstanding"))
    if shares_outstanding is None and current_price not in (None, 0) and market_cap > 0:
        shares_outstanding = market_cap / current_price

    growth_path = _build_growth_path(start_growth, terminal_growth, years=forecast_years)
    margin_path = np.linspace(base_fcf_margin, target_fcf_margin, forecast_years).tolist()

    projected_revenue = latest_revenue
    pv_fcf_total = 0.0
    terminal_value = 0.0
    projection_rows: list[dict[str, float | str | None]] = []

    for year_number, (growth_rate, fcf_margin) in enumerate(zip(growth_path, margin_path), start=1):
        projected_revenue *= 1 + growth_rate
        projected_fcf = projected_revenue * fcf_margin
        discount_factor = (1 + wacc) ** year_number
        pv_fcf = projected_fcf / discount_factor
        pv_fcf_total += pv_fcf

        if year_number == forecast_years:
            terminal_value = projected_fcf * (1 + terminal_growth) / (wacc - terminal_growth)

        projection_rows.append(
            {
                "ticker": row.name,
                "case": case_name,
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
    implied_share_price = equity_value_dcf / shares_outstanding if shares_outstanding not in (None, 0) else np.nan
    upside_downside_pct = (
        ((implied_share_price / current_price) - 1) * 100
        if current_price not in (None, 0) and not pd.isna(implied_share_price)
        else np.nan
    )

    summary_row = {
        "ticker": row.name,
        "case": case_name,
        "company_name": row.get("company_name"),
        "sector_key": _resolve_sector_key(row),
        "latest_revenue": latest_revenue,
        "growth_start_pct": start_growth * 100,
        "target_fcf_margin_pct": target_fcf_margin * 100,
        "wacc_pct": wacc * 100,
        "terminal_growth_pct": terminal_growth * 100,
        "enterprise_value_dcf": enterprise_value_dcf,
        "equity_value_dcf": equity_value_dcf,
        "implied_share_price": implied_share_price,
        "current_price": current_price,
        "upside_downside_pct": upside_downside_pct,
    }
    return summary_row, projection_rows


def _scenario_adjusted_assumptions(
    row: pd.Series,
    base_assumptions: dict[str, float],
) -> dict[str, dict[str, float]]:
    sector_key = _resolve_sector_key(row)
    preset = DEFAULT_SCENARIO_PRESETS.get(sector_key, DEFAULT_SCENARIO_PRESETS["default"])

    scenario_assumptions: dict[str, dict[str, float]] = {}
    for case_name, deltas in preset.items():
        scenario_assumptions[case_name] = {
            "latest_revenue": base_assumptions["latest_revenue"],
            "base_growth_start": _clip(
                base_assumptions["base_growth_start"] + deltas["growth_delta_pct"] / 100,
                0.01,
                0.25,
            ),
            "base_fcf_margin": base_assumptions["base_fcf_margin"],
            "target_fcf_margin": _clip(
                base_assumptions["target_fcf_margin"] + deltas["margin_delta_pct"] / 100,
                0.03,
                0.35,
            ),
            "wacc": _clip(
                base_assumptions["wacc"] + deltas["wacc_delta_pct"] / 100,
                0.06,
                0.18,
            ),
            "terminal_growth": _clip(
                base_assumptions["terminal_growth"] + deltas["terminal_growth_delta_pct"] / 100,
                0.01,
                min(base_assumptions["wacc"] + deltas["wacc_delta_pct"] / 100 - 0.01, 0.05),
            ),
        }
    return scenario_assumptions


def build_dcf_outputs(
    company_snapshots: pd.DataFrame,
    revenue_history: pd.DataFrame,
    macro_snapshot: pd.DataFrame,
    focus_ticker: str | None = None,
    assumptions_file: str | None = None,
    forecast_years: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if company_snapshots.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty

    risk_free = 0.045
    inflation_anchor = 0.025
    high_yield_spread = 0.04

    if not macro_snapshot.empty:
        risk_free = _safe_number(macro_snapshot.loc["US 10Y Treasury Yield", "latest"], 4.5) / 100 if "US 10Y Treasury Yield" in macro_snapshot.index else risk_free
        inflation_anchor = _safe_number(macro_snapshot.loc["US CPI Index", "change_1y"], 2.5) / 100 if "US CPI Index" in macro_snapshot.index else inflation_anchor
        high_yield_spread = _safe_number(macro_snapshot.loc["High Yield Spread", "latest"], 4.0) / 100 if "High Yield Spread" in macro_snapshot.index else high_yield_spread

    terminal_growth = _clip(max(0.02, min(0.035, inflation_anchor if inflation_anchor > 0 else 0.025)), 0.02, 0.035)
    manual_assumptions = _load_assumptions(str(assumptions_file) if assumptions_file else None)

    summary_rows: list[dict[str, float | str | None]] = []
    projection_rows: list[dict[str, float | str | None]] = []
    scenario_rows: list[dict[str, float | str | None]] = []
    scenario_projection_rows: list[dict[str, float | str | None]] = []

    for ticker, row in company_snapshots.iterrows():
        latest_revenue = _safe_number(row.get("latest_revenue"))
        if latest_revenue is None:
            ticker_revenue_history = revenue_history.loc[revenue_history["ticker"] == ticker, "revenue"]
            if not ticker_revenue_history.empty:
                latest_revenue = _safe_number(ticker_revenue_history.iloc[-1])
        if latest_revenue is None:
            continue

        base_assumptions = _derive_base_assumptions(
            row=row,
            latest_revenue=latest_revenue,
            risk_free=risk_free,
            high_yield_spread=high_yield_spread,
            terminal_growth=terminal_growth,
            assumptions=manual_assumptions,
        )

        base_summary, base_projection_rows = _run_dcf_case(
            row=row,
            assumptions=base_assumptions,
            case_name="Base",
            forecast_years=forecast_years,
        )
        base_summary["base_fcf_margin_pct"] = base_assumptions["base_fcf_margin"] * 100
        summary_rows.append(base_summary)
        projection_rows.extend(base_projection_rows)

        scenario_assumptions = _scenario_adjusted_assumptions(row, base_assumptions)
        for case_name, case_assumptions in scenario_assumptions.items():
            scenario_summary, case_projection_rows = _run_dcf_case(
                row=row,
                assumptions=case_assumptions,
                case_name=case_name,
                forecast_years=forecast_years,
            )
            scenario_rows.append(scenario_summary)
            scenario_projection_rows.extend(case_projection_rows)

    dcf_summary = pd.DataFrame(summary_rows).set_index("ticker") if summary_rows else pd.DataFrame()
    dcf_projection = pd.DataFrame(projection_rows)

    if dcf_summary.empty:
        return dcf_summary, dcf_projection, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

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
    dcf_scenarios = pd.DataFrame(scenario_rows)
    dcf_scenario_projection = pd.DataFrame(scenario_projection_rows)
    focus_scenarios = (
        dcf_scenarios.loc[dcf_scenarios["ticker"] == selected_ticker].copy().sort_values("case")
        if not dcf_scenarios.empty
        else pd.DataFrame()
    )
    return dcf_summary, dcf_projection, dcf_sensitivity, dcf_scenarios, focus_scenarios
