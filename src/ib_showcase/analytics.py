from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def _max_drawdown(price_series: pd.Series) -> float:
    clean = price_series.dropna()
    if clean.empty:
        return np.nan
    running_max = clean.cummax()
    drawdown = clean / running_max - 1
    return drawdown.min() * 100


def _percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if higher_is_better:
        return numeric.rank(pct=True, method="average").fillna(0.5) * 100
    return (-numeric).rank(pct=True, method="average").fillna(0.5) * 100


def _value_asof(series: pd.Series, offset: pd.Timedelta) -> float | None:
    clean = series.dropna().sort_index()
    if clean.empty:
        return None
    anchor = clean.index[-1] - offset
    eligible = clean.loc[clean.index <= anchor]
    if eligible.empty:
        return float(clean.iloc[0])
    return float(eligible.iloc[-1])


def build_performance_summary(
    prices: pd.DataFrame,
    benchmark: str,
    risk_free_series: pd.Series | None = None,
) -> pd.DataFrame:
    returns = prices.pct_change().dropna(how="all")
    benchmark_returns = returns[benchmark] if benchmark in returns.columns else None

    latest_risk_free = 0.0
    if risk_free_series is not None and not risk_free_series.dropna().empty:
        latest_risk_free = float(risk_free_series.dropna().iloc[-1]) / 100

    rows: list[dict] = []
    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if len(series) < 2:
            continue

        daily_returns = series.pct_change().dropna()
        total_return = series.iloc[-1] / series.iloc[0] - 1
        annualized_return = (1 + total_return) ** (TRADING_DAYS / len(daily_returns)) - 1
        annualized_vol = daily_returns.std() * np.sqrt(TRADING_DAYS)
        sharpe = np.nan
        if annualized_vol and not np.isnan(annualized_vol):
            sharpe = (annualized_return - latest_risk_free) / annualized_vol

        beta = np.nan
        correlation = np.nan
        if benchmark_returns is not None and ticker != benchmark:
            aligned = pd.concat([daily_returns, benchmark_returns], axis=1, join="inner").dropna()
            if len(aligned) > 5 and aligned.iloc[:, 1].var() != 0:
                beta = aligned.iloc[:, 0].cov(aligned.iloc[:, 1]) / aligned.iloc[:, 1].var()
                correlation = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])

        rows.append(
            {
                "ticker": ticker,
                "total_return_pct": total_return * 100,
                "annualized_return_pct": annualized_return * 100,
                "annualized_vol_pct": annualized_vol * 100,
                "sharpe_like": sharpe,
                "max_drawdown_pct": _max_drawdown(series),
                "beta_vs_benchmark": beta,
                "correlation_vs_benchmark": correlation,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "total_return_pct",
                "annualized_return_pct",
                "annualized_vol_pct",
                "sharpe_like",
                "max_drawdown_pct",
                "beta_vs_benchmark",
                "correlation_vs_benchmark",
            ]
        )

    summary = pd.DataFrame(rows).set_index("ticker").sort_values(
        "annualized_return_pct", ascending=False
    )
    return summary


def build_screening_table(
    performance_summary: pd.DataFrame,
    company_snapshots: pd.DataFrame,
    benchmark: str,
) -> pd.DataFrame:
    merged = company_snapshots.join(performance_summary, how="left")
    peer_table = merged.drop(index=benchmark, errors="ignore").copy()
    if peer_table.empty:
        return peer_table

    peer_table["momentum_score"] = _percentile_score(
        peer_table["annualized_return_pct"], higher_is_better=True
    )
    peer_table["quality_score"] = (
        _percentile_score(peer_table["roe_pct"], higher_is_better=True) * 0.4
        + _percentile_score(peer_table["operating_margin_pct"], higher_is_better=True) * 0.3
        + _percentile_score(peer_table["revenue_cagr_3y_pct"], higher_is_better=True) * 0.3
    )
    peer_table["value_score"] = (
        _percentile_score(peer_table["trailing_pe"], higher_is_better=False) * 0.4
        + _percentile_score(peer_table["enterprise_to_ebitda"], higher_is_better=False) * 0.3
        + _percentile_score(peer_table["price_to_book"], higher_is_better=False) * 0.3
    )
    peer_table["defensiveness_score"] = (
        _percentile_score(peer_table["annualized_vol_pct"], higher_is_better=False) * 0.5
        + _percentile_score(peer_table["max_drawdown_pct"], higher_is_better=True) * 0.2
        + _percentile_score(peer_table["debt_to_equity"], higher_is_better=False) * 0.3
    )
    peer_table["composite_score"] = (
        peer_table["momentum_score"] * 0.25
        + peer_table["quality_score"] * 0.35
        + peer_table["value_score"] * 0.25
        + peer_table["defensiveness_score"] * 0.15
    )

    ordered_columns = [
        "company_name",
        "sector",
        "industry",
        "market_cap",
        "current_price",
        "total_return_pct",
        "annualized_return_pct",
        "annualized_vol_pct",
        "max_drawdown_pct",
        "beta_vs_benchmark",
        "trailing_pe",
        "forward_pe",
        "price_to_book",
        "enterprise_to_revenue",
        "enterprise_to_ebitda",
        "roe_pct",
        "operating_margin_pct",
        "ebitda_margin_pct",
        "revenue_growth_pct",
        "revenue_cagr_3y_pct",
        "debt_to_equity",
        "net_debt_to_ebitda",
        "momentum_score",
        "quality_score",
        "value_score",
        "defensiveness_score",
        "composite_score",
    ]

    existing_columns = [column for column in ordered_columns if column in peer_table.columns]
    return peer_table[existing_columns].sort_values("composite_score", ascending=False)


def build_macro_snapshot(macro_data: pd.DataFrame) -> pd.DataFrame:
    if macro_data.empty:
        return pd.DataFrame(columns=["latest", "change_30d", "change_1y"])

    snapshot_rows: list[dict] = []
    for column in macro_data.columns:
        series = macro_data[column].dropna()
        if series.empty:
            continue

        latest = series.iloc[-1]
        value_30d = _value_asof(series, pd.Timedelta(days=30))
        value_1y = _value_asof(series, pd.Timedelta(days=365))
        change_30d = latest - value_30d if value_30d is not None else np.nan
        change_1y = latest - value_1y if value_1y is not None else np.nan
        snapshot_rows.append(
            {
                "series": column,
                "latest": latest,
                "change_30d": change_30d,
                "change_1y": change_1y,
            }
        )

    if not snapshot_rows:
        return pd.DataFrame(columns=["latest", "change_30d", "change_1y"])

    return pd.DataFrame(snapshot_rows).set_index("series").sort_index()


def build_transformed_macro_snapshot(macro_data: pd.DataFrame) -> pd.DataFrame:
    if macro_data.empty:
        return pd.DataFrame(columns=["latest", "change_30d", "change_1y", "display_unit"])

    rows: list[dict] = []
    for column in macro_data.columns:
        series = macro_data[column].dropna()
        if series.empty:
            continue

        latest = float(series.iloc[-1])
        value_30d = _value_asof(series, pd.Timedelta(days=30))
        value_1y = _value_asof(series, pd.Timedelta(days=365))
        if column == "US CPI Index":
            trailing_index = value_1y
            yoy_change_pct = ((latest / trailing_index) - 1) * 100 if trailing_index else np.nan
            rows.append(
                {
                    "series": column,
                    "latest": latest,
                    "change_30d": latest - value_30d if value_30d is not None else np.nan,
                    "change_1y": yoy_change_pct,
                    "display_unit": "index / YoY %",
                }
            )
        elif "Yield" in column or "Rate" in column or "Spread" in column or "Treasury" in column:
            rows.append(
                {
                    "series": column,
                    "latest": latest,
                    "change_30d": (latest - value_30d) * 100 if value_30d is not None else np.nan,
                    "change_1y": (latest - value_1y) * 100 if value_1y is not None else np.nan,
                    "display_unit": "level %, changes in bps",
                }
            )
        else:
            rows.append(
                {
                    "series": column,
                    "latest": latest,
                    "change_30d": latest - value_30d if value_30d is not None else np.nan,
                    "change_1y": latest - value_1y if value_1y is not None else np.nan,
                    "display_unit": "level change",
                }
            )

    return pd.DataFrame(rows).set_index("series").sort_index()


def build_macro_factor_series(macro_data: pd.DataFrame) -> pd.DataFrame:
    if macro_data.empty:
        return pd.DataFrame()

    prepared = macro_data.sort_index().ffill()
    factors = pd.DataFrame(index=prepared.index)
    if "US 10Y Treasury Yield" in prepared.columns:
        factors["10y_yield_change_bps"] = prepared["US 10Y Treasury Yield"].diff() * 100
    if "High Yield Spread" in prepared.columns:
        factors["hy_spread_change_bps"] = prepared["High Yield Spread"].diff() * 100
    if "Fed Funds Rate" in prepared.columns:
        factors["fed_funds_change_bps"] = prepared["Fed Funds Rate"].diff() * 100
    if "US CPI Index" in prepared.columns:
        factors["cpi_yoy_pct"] = prepared["US CPI Index"].pct_change(252) * 100
    if "US Unemployment Rate" in prepared.columns:
        factors["unemployment_change_pp"] = prepared["US Unemployment Rate"].diff()
    return factors.dropna(how="all")


def build_macro_factor_correlation(
    prices: pd.DataFrame,
    macro_data: pd.DataFrame,
    benchmark: str,
) -> pd.DataFrame:
    macro_factors = build_macro_factor_series(macro_data)
    if prices.empty or macro_factors.empty:
        return pd.DataFrame()

    daily_returns = prices.drop(columns=[benchmark], errors="ignore").pct_change().dropna(how="all")
    combined = daily_returns.join(macro_factors, how="inner")
    if combined.empty:
        return pd.DataFrame()

    ticker_columns = daily_returns.columns.tolist()
    factor_columns = macro_factors.columns.tolist()
    correlations = combined[ticker_columns + factor_columns].corr().loc[ticker_columns, factor_columns]
    return correlations


def build_sec_enhanced_screening_table(
    screening_table: pd.DataFrame,
    sec_snapshot: pd.DataFrame,
) -> pd.DataFrame:
    if screening_table.empty:
        return screening_table

    merged = screening_table.join(sec_snapshot, how="left")
    if "latest_sec_revenue" in merged.columns and "latest_sec_net_income" in merged.columns:
        merged["sec_net_margin_pct"] = (
            merged["latest_sec_net_income"] / merged["latest_sec_revenue"] * 100
        )
    if "last_10q_filed" in merged.columns:
        merged["days_since_last_10q"] = (
            pd.Timestamp.today().normalize() - pd.to_datetime(merged["last_10q_filed"], errors="coerce")
        ).dt.days
    if "last_10k_filed" in merged.columns:
        merged["days_since_last_10k"] = (
            pd.Timestamp.today().normalize() - pd.to_datetime(merged["last_10k_filed"], errors="coerce")
        ).dt.days
    return merged


def build_filing_reaction_table(
    sec_filings: pd.DataFrame,
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
    benchmark: str,
) -> pd.DataFrame:
    if sec_filings.empty or prices.empty:
        return pd.DataFrame()

    relevant_forms = {
        "10-Q",
        "10-K",
        "8-K",
        "8-K/A",
        "20-F",
        "40-F",
        "6-K",
        "DEF 14A",
        "S-1",
        "S-3",
        "S-3ASR",
    }
    filtered_filings = sec_filings.loc[sec_filings["form"].isin(relevant_forms)].copy()
    if filtered_filings.empty:
        return pd.DataFrame()
    filtered_filings = filtered_filings.sort_values(
        ["ticker", "filing_date", "acceptance_datetime"]
    ).drop_duplicates(subset=["ticker", "form", "filing_date"], keep="last")

    trading_index = pd.Index(prices.index)
    reaction_rows: list[dict] = []

    for _, filing in filtered_filings.iterrows():
        ticker = filing["ticker"]
        if ticker not in prices.columns:
            continue

        filing_date = pd.Timestamp(filing["filing_date"])
        acceptance_datetime = filing.get("acceptance_datetime")
        trade_anchor = filing_date
        if pd.notna(acceptance_datetime):
            acceptance_ts = pd.Timestamp(acceptance_datetime).tz_convert(None)
            if acceptance_ts.hour >= 16:
                trade_anchor = acceptance_ts.normalize() + pd.Timedelta(days=1)

        event_idx = trading_index.searchsorted(trade_anchor)
        if event_idx >= len(trading_index) or event_idx == 0:
            continue

        event_date = trading_index[event_idx]
        prev_date = trading_index[event_idx - 1]
        next_3_idx = min(event_idx + 3, len(trading_index) - 1)
        next_5_idx = min(event_idx + 5, len(trading_index) - 1)

        stock_prev = prices.at[prev_date, ticker]
        stock_event = prices.at[event_date, ticker]
        stock_3d = prices.iat[next_3_idx, prices.columns.get_loc(ticker)]
        stock_5d = prices.iat[next_5_idx, prices.columns.get_loc(ticker)]

        benchmark_prev = prices.at[prev_date, benchmark] if benchmark in prices.columns else np.nan
        benchmark_event = prices.at[event_date, benchmark] if benchmark in prices.columns else np.nan
        benchmark_3d = prices.iat[next_3_idx, prices.columns.get_loc(benchmark)] if benchmark in prices.columns else np.nan
        benchmark_5d = prices.iat[next_5_idx, prices.columns.get_loc(benchmark)] if benchmark in prices.columns else np.nan

        stock_day0 = (stock_event / stock_prev - 1) * 100 if stock_prev else np.nan
        stock_3day = (stock_3d / stock_prev - 1) * 100 if stock_prev else np.nan
        stock_5day = (stock_5d / stock_prev - 1) * 100 if stock_prev else np.nan
        benchmark_day0 = (benchmark_event / benchmark_prev - 1) * 100 if benchmark_prev else np.nan
        benchmark_3day = (benchmark_3d / benchmark_prev - 1) * 100 if benchmark_prev else np.nan
        benchmark_5day = (benchmark_5d / benchmark_prev - 1) * 100 if benchmark_prev else np.nan

        volume_ratio = np.nan
        if ticker in volumes.columns:
            trailing_volume = volumes[ticker].iloc[max(0, event_idx - 20) : event_idx].mean()
            if trailing_volume and not pd.isna(trailing_volume):
                volume_ratio = volumes.at[event_date, ticker] / trailing_volume

        reaction_rows.append(
            {
                "ticker": ticker,
                "form": filing["form"],
                "filing_date": filing_date,
                "event_trade_date": event_date,
                "acceptance_datetime": acceptance_datetime,
                "filing_url": filing.get("filing_url"),
                "stock_return_day0_pct": stock_day0,
                "stock_return_3d_pct": stock_3day,
                "stock_return_5d_pct": stock_5day,
                "benchmark_return_day0_pct": benchmark_day0,
                "benchmark_return_3d_pct": benchmark_3day,
                "benchmark_return_5d_pct": benchmark_5day,
                "excess_return_day0_pct": stock_day0 - benchmark_day0,
                "excess_return_3d_pct": stock_3day - benchmark_3day,
                "excess_return_5d_pct": stock_5day - benchmark_5day,
                "volume_ratio_vs_20d": volume_ratio,
            }
        )

    if not reaction_rows:
        return pd.DataFrame()

    return pd.DataFrame(reaction_rows).sort_values(["ticker", "filing_date"], ascending=[True, False])


def build_filing_event_summary(filing_reactions: pd.DataFrame) -> pd.DataFrame:
    if filing_reactions.empty:
        return pd.DataFrame()

    summary = (
        filing_reactions.groupby("form")
        .agg(
            event_count=("ticker", "count"),
            avg_excess_day0_pct=("excess_return_day0_pct", "mean"),
            avg_abs_excess_day0_pct=("excess_return_day0_pct", lambda s: s.abs().mean()),
            avg_excess_3d_pct=("excess_return_3d_pct", "mean"),
            avg_volume_ratio=("volume_ratio_vs_20d", "mean"),
        )
        .sort_values("avg_abs_excess_day0_pct", ascending=False)
    )
    return summary
