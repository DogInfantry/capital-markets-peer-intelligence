from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def _apply_theme() -> None:
    sns.set_theme(style="whitegrid", palette="deep")
    plt.rcParams["figure.figsize"] = (12, 7)
    plt.rcParams["axes.titlesize"] = 15
    plt.rcParams["axes.labelsize"] = 11


def _finalize_chart(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close()
    return output_path


def plot_normalized_returns(
    prices: pd.DataFrame,
    benchmark: str,
    sector_label: str,
    output_path: Path,
) -> Path:
    _apply_theme()
    normalized = prices.div(prices.ffill().bfill().iloc[0]).mul(100)
    ax = normalized.plot(linewidth=2)
    ax.set_title(f"{sector_label}: Normalized Price Performance")
    ax.set_ylabel("Indexed to 100")
    ax.set_xlabel("")
    for line in ax.get_lines():
        if line.get_label() == benchmark:
            line.set_linewidth(3)
            line.set_alpha(0.95)
    return _finalize_chart(output_path)


def plot_risk_return_scatter(
    performance_summary: pd.DataFrame,
    benchmark: str,
    output_path: Path,
) -> Path:
    _apply_theme()
    plot_df = performance_summary.drop(index=benchmark, errors="ignore").copy()
    if plot_df.empty:
        plt.figure()
        plt.text(0.5, 0.5, "Risk/return data unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)
    ax = sns.scatterplot(
        data=plot_df,
        x="annualized_vol_pct",
        y="annualized_return_pct",
        size="sharpe_like",
        sizes=(80, 350),
        legend=False,
    )
    for ticker, row in plot_df.iterrows():
        ax.text(row["annualized_vol_pct"] + 0.2, row["annualized_return_pct"] + 0.2, ticker)
    ax.set_title("Risk / Return Positioning")
    ax.set_xlabel("Annualized Volatility (%)")
    ax.set_ylabel("Annualized Return (%)")
    return _finalize_chart(output_path)


def plot_valuation_bars(company_snapshots: pd.DataFrame, output_path: Path) -> Path:
    _apply_theme()
    chart_df = company_snapshots.reset_index()[
        ["ticker", "trailing_pe", "enterprise_to_ebitda", "price_to_book"]
    ]
    melted = chart_df.melt(id_vars="ticker", var_name="metric", value_name="value").dropna()
    if melted.empty:
        plt.figure()
        plt.text(0.5, 0.5, "Valuation fields unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)
    ax = sns.barplot(data=melted, x="ticker", y="value", hue="metric")
    ax.set_title("Valuation Multiples Comparison")
    ax.set_xlabel("")
    ax.set_ylabel("Multiple")
    return _finalize_chart(output_path)


def plot_quality_value_matrix(screening_table: pd.DataFrame, output_path: Path) -> Path:
    _apply_theme()
    if screening_table.empty:
        plt.figure()
        plt.text(0.5, 0.5, "Screening data unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)
    ax = sns.scatterplot(
        data=screening_table,
        x="value_score",
        y="quality_score",
        size="market_cap",
        sizes=(100, 900),
        hue="composite_score",
        palette="viridis",
    )
    for ticker, row in screening_table.iterrows():
        ax.text(row["value_score"] + 0.7, row["quality_score"] + 0.7, ticker)
    ax.set_title("Quality vs. Value Positioning")
    ax.set_xlabel("Value Score")
    ax.set_ylabel("Quality Score")
    return _finalize_chart(output_path)


def plot_correlation_heatmap(prices: pd.DataFrame, output_path: Path) -> Path:
    _apply_theme()
    correlation_matrix = prices.pct_change().dropna(how="all").corr()
    if correlation_matrix.empty:
        plt.figure()
        plt.text(0.5, 0.5, "Correlation data unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)
    ax = sns.heatmap(correlation_matrix, annot=True, cmap="Blues", vmin=-1, vmax=1)
    ax.set_title("Peer Correlation Heatmap")
    return _finalize_chart(output_path)


def plot_macro_dashboard(macro_data: pd.DataFrame, output_path: Path) -> Path:
    _apply_theme()
    available_columns = list(macro_data.columns[:4])
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    if not available_columns:
        for axis in axes.flatten():
            axis.axis("off")
        fig.text(0.5, 0.5, "Macro data unavailable", ha="center", va="center")
        return _finalize_chart(output_path)
    for axis, column in zip(axes.flatten(), available_columns):
        axis.plot(macro_data.index, macro_data[column], linewidth=2)
        axis.set_title(column)
        axis.set_xlabel("")
    for axis in axes.flatten()[len(available_columns) :]:
        axis.axis("off")
    fig.suptitle("Macro Dashboard", fontsize=16, y=1.02)
    return _finalize_chart(output_path)


def plot_revenue_trends(revenue_history: pd.DataFrame, output_path: Path) -> Path:
    _apply_theme()
    if revenue_history.empty:
        plt.figure()
        plt.text(0.5, 0.5, "Revenue history unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)

    ax = sns.lineplot(data=revenue_history, x="year", y="revenue", hue="ticker", marker="o")
    ax.set_title("Revenue Trend by Company")
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel("Revenue")
    return _finalize_chart(output_path)


def plot_scorecard_bars(screening_table: pd.DataFrame, output_path: Path) -> Path:
    _apply_theme()
    if screening_table.empty:
        plt.figure()
        plt.text(0.5, 0.5, "Scorecard data unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)

    chart_df = (
        screening_table[["momentum_score", "quality_score", "value_score", "defensiveness_score"]]
        .head(6)
        .reset_index()
        .melt(id_vars="ticker", var_name="score_type", value_name="score")
    )
    ax = sns.barplot(data=chart_df, x="ticker", y="score", hue="score_type")
    ax.set_title("Peer Scorecard Comparison")
    ax.set_xlabel("")
    ax.set_ylabel("Score")
    return _finalize_chart(output_path)


def plot_dcf_upside_bars(dcf_summary: pd.DataFrame, output_path: Path) -> Path:
    _apply_theme()
    if dcf_summary.empty:
        plt.figure()
        plt.text(0.5, 0.5, "DCF output unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)

    chart_df = dcf_summary.reset_index().sort_values("upside_downside_pct", ascending=False)
    ax = sns.barplot(
        data=chart_df,
        x="ticker",
        y="upside_downside_pct",
        hue="ticker",
        palette="crest",
        legend=False,
    )
    ax.axhline(0, color="black", linewidth=1)
    ax.set_title("DCF Implied Upside / Downside")
    ax.set_xlabel("")
    ax.set_ylabel("Upside / Downside (%)")
    return _finalize_chart(output_path)


def plot_dcf_sensitivity_heatmap(
    dcf_sensitivity: pd.DataFrame,
    focus_ticker: str | None,
    output_path: Path,
) -> Path:
    _apply_theme()
    if dcf_sensitivity.empty:
        plt.figure()
        plt.text(0.5, 0.5, "DCF sensitivity unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)

    pivot_table = dcf_sensitivity.pivot(
        index="terminal_growth_pct",
        columns="wacc_pct",
        values="implied_share_price",
    )
    ax = sns.heatmap(pivot_table, annot=True, fmt=".1f", cmap="YlGnBu")
    title = "DCF Sensitivity"
    if focus_ticker:
        title = f"DCF Sensitivity: {focus_ticker}"
    ax.set_title(title)
    ax.set_xlabel("WACC (%)")
    ax.set_ylabel("Terminal Growth (%)")
    return _finalize_chart(output_path)


def plot_dcf_scenario_cases(
    focus_scenarios: pd.DataFrame,
    focus_ticker: str | None,
    output_path: Path,
) -> Path:
    _apply_theme()
    if focus_scenarios.empty:
        plt.figure()
        plt.text(0.5, 0.5, "DCF scenario cases unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)

    order = ["Bear", "Base", "Bull"]
    chart_df = focus_scenarios.copy()
    chart_df["case"] = pd.Categorical(chart_df["case"], categories=order, ordered=True)
    chart_df = chart_df.sort_values("case")
    ax = sns.barplot(data=chart_df, x="case", y="implied_share_price", hue="case", legend=False, palette="Set2")
    ax.set_title(f"Sector Scenario DCF Cases{f': {focus_ticker}' if focus_ticker else ''}")
    ax.set_xlabel("")
    ax.set_ylabel("Implied Share Price")
    return _finalize_chart(output_path)


def plot_macro_factor_heatmap(
    macro_factor_correlation: pd.DataFrame,
    output_path: Path,
) -> Path:
    _apply_theme()
    if macro_factor_correlation.empty:
        plt.figure()
        plt.text(0.5, 0.5, "Macro factor correlation unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)

    ax = sns.heatmap(
        macro_factor_correlation,
        annot=True,
        cmap="RdBu",
        center=0,
        fmt=".2f",
    )
    ax.set_title("Peer Return Correlation vs. Macro Factors")
    ax.set_xlabel("Macro Factor")
    ax.set_ylabel("Ticker")
    return _finalize_chart(output_path)


def plot_filing_reaction_bars(
    filing_reactions: pd.DataFrame,
    focus_ticker: str | None,
    output_path: Path,
) -> Path:
    _apply_theme()
    if filing_reactions.empty:
        plt.figure()
        plt.text(0.5, 0.5, "Filing reaction data unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)

    chart_df = filing_reactions.copy()
    if focus_ticker:
        filtered = chart_df[chart_df["ticker"] == focus_ticker]
        if not filtered.empty:
            chart_df = filtered
    chart_df = chart_df.sort_values("filing_date").tail(8)
    chart_df["label"] = chart_df["form"] + " " + chart_df["filing_date"].dt.strftime("%Y-%m-%d")
    ax = sns.barplot(data=chart_df, x="label", y="excess_return_day0_pct", hue="form")
    ax.axhline(0, color="black", linewidth=1)
    ax.set_title(f"Filing-Day Excess Returns{f': {focus_ticker}' if focus_ticker else ''}")
    ax.set_xlabel("")
    ax.set_ylabel("Excess Return Day 0 (%)")
    plt.xticks(rotation=35, ha="right")
    return _finalize_chart(output_path)


def plot_sec_quarterly_trends(
    sec_quarterly_fundamentals: pd.DataFrame,
    focus_ticker: str | None,
    output_path: Path,
) -> Path:
    _apply_theme()
    if sec_quarterly_fundamentals.empty:
        plt.figure()
        plt.text(0.5, 0.5, "SEC quarterly fundamentals unavailable", ha="center", va="center")
        plt.axis("off")
        return _finalize_chart(output_path)

    chart_df = sec_quarterly_fundamentals.copy()
    if focus_ticker:
        filtered = chart_df[chart_df["ticker"] == focus_ticker]
        if not filtered.empty:
            chart_df = filtered

    chart_df = chart_df.sort_values("end").tail(10)
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    sns.lineplot(data=chart_df, x="end", y="revenue", hue="ticker", marker="o", ax=axes[0])
    axes[0].set_title(f"SEC Revenue Trend{f': {focus_ticker}' if focus_ticker else ''}")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Revenue")

    sns.lineplot(data=chart_df, x="end", y="net_income", hue="ticker", marker="o", ax=axes[1], legend=False)
    axes[1].set_title("SEC Net Income Trend")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Net Income")
    return _finalize_chart(output_path)
