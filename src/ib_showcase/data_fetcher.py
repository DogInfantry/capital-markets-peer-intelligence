from __future__ import annotations

from typing import Iterable

import pandas as pd
import yfinance as yf
from pandas_datareader import data as web

from ib_showcase.config import ProjectConfig


def _configure_yfinance_cache(config: ProjectConfig) -> None:
    cache_dir = config.output_dir / ".yfinance_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yf.set_tz_cache_location(str(cache_dir))
    except Exception:
        pass


def _coalesce(mapping: dict, keys: Iterable[str]) -> float | str | None:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _extract_statement_series(frame: pd.DataFrame, row_names: list[str]) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="float64")

    for row_name in row_names:
        if row_name in frame.index:
            series = frame.loc[row_name]
            series.index = pd.to_datetime(series.index)
            return series.sort_index()

    return pd.Series(dtype="float64")


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def fetch_price_history(config: ProjectConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    _configure_yfinance_cache(config)
    symbols = list(dict.fromkeys(config.tickers + [config.benchmark]))
    raw = yf.download(
        tickers=symbols,
        start=config.start,
        end=config.end,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )

    if raw.empty:
        raise ValueError("No price data returned. Check tickers or date range.")

    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"].copy()
        volumes = raw["Volume"].copy()
    else:
        single_symbol = symbols[0]
        prices = raw[["Close"]].rename(columns={"Close": single_symbol})
        volumes = raw[["Volume"]].rename(columns={"Volume": single_symbol})

    prices.index = pd.to_datetime(prices.index)
    volumes.index = pd.to_datetime(volumes.index)

    prices = prices.dropna(how="all").sort_index()
    volumes = volumes.dropna(how="all").sort_index()
    return prices, volumes


def fetch_company_snapshots(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    snapshots: list[dict] = []
    revenue_frames: list[pd.DataFrame] = []

    for ticker in tickers:
        instrument = yf.Ticker(ticker)
        try:
            info = instrument.info or {}
        except Exception:
            info = {}

        try:
            income_statement = instrument.income_stmt
        except Exception:
            income_statement = pd.DataFrame()

        try:
            cash_flow = instrument.cashflow
        except Exception:
            cash_flow = pd.DataFrame()

        try:
            balance_sheet = instrument.balance_sheet
        except Exception:
            balance_sheet = pd.DataFrame()

        revenue_series = _extract_statement_series(
            income_statement, ["Total Revenue", "Operating Revenue"]
        )
        ebitda_series = _extract_statement_series(income_statement, ["EBITDA"])
        operating_income_series = _extract_statement_series(
            income_statement, ["Operating Income"]
        )
        fcf_series = _extract_statement_series(cash_flow, ["Free Cash Flow"])
        debt_series = _extract_statement_series(balance_sheet, ["Total Debt"])
        cash_series = _extract_statement_series(
            balance_sheet,
            [
                "Cash And Cash Equivalents",
                "Cash Cash Equivalents And Short Term Investments",
            ],
        )

        latest_revenue = revenue_series.iloc[-1] if not revenue_series.empty else None
        oldest_revenue = revenue_series.iloc[0] if len(revenue_series) >= 2 else None
        periods = max(len(revenue_series) - 1, 1)
        revenue_cagr = None
        if oldest_revenue not in (None, 0) and latest_revenue is not None and len(revenue_series) >= 2:
            revenue_cagr = (latest_revenue / oldest_revenue) ** (1 / periods) - 1

        latest_ebitda = ebitda_series.iloc[-1] if not ebitda_series.empty else None
        latest_operating_income = (
            operating_income_series.iloc[-1] if not operating_income_series.empty else None
        )
        latest_fcf = fcf_series.iloc[-1] if not fcf_series.empty else None
        latest_debt = debt_series.iloc[-1] if not debt_series.empty else None
        latest_cash = cash_series.iloc[-1] if not cash_series.empty else None

        snapshot = {
            "ticker": ticker,
            "company_name": _coalesce(info, ["shortName", "longName"]) or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "current_price": _coalesce(info, ["currentPrice", "regularMarketPrice"]),
            "target_mean_price": info.get("targetMeanPrice"),
            "beta": info.get("beta"),
            "shares_outstanding": _coalesce(info, ["sharesOutstanding", "impliedSharesOutstanding"]),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "enterprise_to_revenue": info.get("enterpriseToRevenue"),
            "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
            "operating_margin_pct": (
                info.get("operatingMargins") * 100 if info.get("operatingMargins") is not None else None
            ),
            "ebitda_margin_pct": (
                info.get("ebitdaMargins") * 100 if info.get("ebitdaMargins") is not None else None
            ),
            "roe_pct": info.get("returnOnEquity") * 100 if info.get("returnOnEquity") is not None else None,
            "revenue_growth_pct": (
                info.get("revenueGrowth") * 100 if info.get("revenueGrowth") is not None else None
            ),
            "debt_to_equity": info.get("debtToEquity"),
            "employees": info.get("fullTimeEmployees"),
            "latest_revenue": latest_revenue,
            "latest_ebitda": latest_ebitda,
            "latest_operating_income": latest_operating_income,
            "latest_free_cash_flow": latest_fcf,
            "latest_total_debt": latest_debt,
            "latest_cash": latest_cash,
            "revenue_cagr_3y_pct": revenue_cagr * 100 if revenue_cagr is not None else None,
            "net_debt_to_ebitda": _safe_ratio(
                (latest_debt - latest_cash) if latest_debt is not None and latest_cash is not None else None,
                latest_ebitda,
            ),
        }
        snapshots.append(snapshot)

        if not revenue_series.empty:
            revenue_frames.append(
                pd.DataFrame(
                    {
                        "date": revenue_series.index,
                        "ticker": ticker,
                        "revenue": revenue_series.values,
                    }
                )
            )

    snapshot_df = pd.DataFrame(snapshots).set_index("ticker").sort_index()

    if revenue_frames:
        revenue_history = pd.concat(revenue_frames, ignore_index=True)
        revenue_history["year"] = revenue_history["date"].dt.year
        revenue_history = revenue_history.sort_values(["ticker", "date"])
    else:
        revenue_history = pd.DataFrame(columns=["date", "ticker", "revenue", "year"])

    return snapshot_df, revenue_history


def fetch_macro_series(config: ProjectConfig) -> pd.DataFrame:
    fred_codes = list(config.fred_series.values())
    macro_data = web.DataReader(fred_codes, "fred", start=config.start, end=config.end)
    macro_data = macro_data.rename(
        columns={code: label for label, code in config.fred_series.items()}
    )
    macro_data.index = pd.to_datetime(macro_data.index)
    return macro_data.sort_index()
