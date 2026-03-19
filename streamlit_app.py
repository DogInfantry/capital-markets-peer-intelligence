from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ib_showcase.config import ProjectConfig  # noqa: E402
from ib_showcase.pipeline import run_analysis_pipeline  # noqa: E402


st.set_page_config(
    page_title="IB Recruiting Dashboard",
    layout="wide",
)

st.title("IB Recruiting Dashboard")
st.caption(
    "Free-data peer benchmarking, valuation analysis, DCF output, and recruiter-ready storytelling."
)

with st.sidebar:
    st.header("Analysis Inputs")
    tickers_input = st.text_input("Peer tickers", "GS,MS,JPM,BAC,C")
    benchmark = st.text_input("Benchmark", "^GSPC")
    start_date = st.text_input("Start date", "2021-01-01")
    end_date = st.text_input("End date", "")
    sector_label = st.text_input("Sector label", "Investment Banking Peer Set")
    output_dir = st.text_input("Output directory", "outputs")
    assumptions_file = st.text_input("DCF assumptions CSV", "templates/dcf_assumptions_template.csv")
    run_button = st.button("Run Analysis", type="primary")


def _download_button(label: str, dataframe: pd.DataFrame, filename: str) -> None:
    st.download_button(
        label=label,
        data=dataframe.to_csv(index=True).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


if run_button:
    tickers = [ticker.strip().upper() for ticker in tickers_input.split(",") if ticker.strip()]
    config = ProjectConfig(
        tickers=tickers,
        benchmark=benchmark.strip(),
        start=start_date.strip(),
        end=end_date.strip() or None,
        sector_label=sector_label.strip(),
        output_dir=Path(output_dir.strip()),
        assumptions_file=Path(assumptions_file.strip()) if assumptions_file.strip() else None,
    )

    with st.spinner("Building market, comps, and DCF analysis..."):
        results = run_analysis_pipeline(config=config, write_outputs=True)

    screening_table = results["screening_table"]
    performance_summary = results["performance_summary"]
    macro_snapshot = results["macro_snapshot"]
    dcf_summary = results["dcf_summary"]
    dcf_projection = results["dcf_projection"]
    dcf_sensitivity = results["dcf_sensitivity"]
    dcf_scenarios = results["dcf_scenarios"]
    focus_scenarios = results["focus_scenarios"]
    sec_snapshot = results["sec_snapshot"]
    sec_filings = results["sec_filings"]
    sec_quarterly_fundamentals = results["sec_quarterly_fundamentals"]
    filing_reactions = results["filing_reactions"]
    filing_event_summary = results["filing_event_summary"]
    macro_factor_correlation = results["macro_factor_correlation"]
    transformed_macro_snapshot = results["transformed_macro_snapshot"]
    focus_ticker = results["focus_ticker"]
    output_dirs = results["output_dirs"]

    st.success(f"Outputs written to {output_dirs['base']}")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Peer Count", len(config.tickers))
    metric_cols[1].metric("Top Ranked", screening_table.index[0] if not screening_table.empty else "n/a")
    metric_cols[2].metric("DCF Focus", focus_ticker or "n/a")
    metric_cols[3].metric("Best DCF Upside", f"{dcf_summary.iloc[0]['upside_downside_pct']:.1f}%" if not dcf_summary.empty and pd.notna(dcf_summary.iloc[0]['upside_downside_pct']) else "n/a")

    st.subheader("Scorecard Overview")
    if not screening_table.empty:
        scorecard_df = (
            screening_table[["momentum_score", "quality_score", "value_score", "defensiveness_score"]]
            .reset_index()
            .melt(id_vars="ticker", var_name="score_type", value_name="score")
        )
        st.plotly_chart(
            px.bar(
                scorecard_df,
                x="ticker",
                y="score",
                color="score_type",
                barmode="group",
                title="Peer Scorecard Comparison",
            ),
            use_container_width=True,
        )

    chart_left, chart_right = st.columns(2)

    with chart_left:
        st.subheader("Risk / Return")
        if not performance_summary.empty:
            risk_df = performance_summary.drop(index=config.benchmark, errors="ignore").reset_index()
            if "sharpe_like" in risk_df.columns:
                risk_df["sharpe_like"] = risk_df["sharpe_like"].fillna(0.1).clip(lower=0.1)
            fig = px.scatter(
                risk_df,
                x="annualized_vol_pct",
                y="annualized_return_pct",
                text="ticker",
                size="sharpe_like",
                color="annualized_return_pct",
                title="Risk / Return Positioning",
            )
            fig.update_traces(textposition="top center")
            st.plotly_chart(fig, use_container_width=True)

    with chart_right:
        st.subheader("DCF Upside / Downside")
        if not dcf_summary.empty:
            dcf_chart_df = dcf_summary.reset_index().sort_values("upside_downside_pct", ascending=False)
            st.plotly_chart(
                px.bar(
                    dcf_chart_df,
                    x="ticker",
                    y="upside_downside_pct",
                    color="upside_downside_pct",
                    title="DCF Implied Upside / Downside",
                ),
                use_container_width=True,
            )

    st.subheader("Sector Scenario Cases")
    if not focus_scenarios.empty:
        scenario_chart_df = focus_scenarios.copy()
        st.plotly_chart(
            px.bar(
                scenario_chart_df,
                x="case",
                y="implied_share_price",
                color="case",
                title=f"Bear / Base / Bull Scenarios: {focus_ticker}",
            ),
            use_container_width=True,
        )

    st.subheader("Normalized Returns")
    if not results["prices"].empty:
        normalized = results["prices"].div(results["prices"].ffill().bfill().iloc[0]).mul(100)
        st.plotly_chart(
            px.line(
                normalized.reset_index(),
                x=normalized.reset_index().columns[0],
                y=normalized.columns,
                title=f"{config.sector_label}: Indexed Performance",
            ),
            use_container_width=True,
        )

    lower_left, lower_right = st.columns(2)

    with lower_left:
        st.subheader("Macro Snapshot")
        st.dataframe(transformed_macro_snapshot, use_container_width=True)

    with lower_right:
        st.subheader("DCF Sensitivity")
        if not dcf_sensitivity.empty:
            pivot = dcf_sensitivity.pivot(
                index="terminal_growth_pct",
                columns="wacc_pct",
                values="implied_share_price",
            )
            st.dataframe(pivot, use_container_width=True)

    event_left, event_right = st.columns(2)

    with event_left:
        st.subheader("Filing Event Summary")
        st.dataframe(filing_event_summary, use_container_width=True)

    with event_right:
        st.subheader("SEC Snapshot")
        st.dataframe(sec_snapshot, use_container_width=True)

    st.subheader("Macro Factor Correlation")
    st.dataframe(macro_factor_correlation, use_container_width=True)

    st.subheader("Tables")
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        ["Screening", "Performance", "DCF", "Projection", "Scenarios", "SEC Filings", "Filing Reactions", "SEC Quarterlies"]
    )
    with tab1:
        st.dataframe(screening_table, use_container_width=True)
        _download_button("Download screening CSV", screening_table, "screening_table.csv")
    with tab2:
        st.dataframe(performance_summary, use_container_width=True)
        _download_button("Download performance CSV", performance_summary, "performance_summary.csv")
    with tab3:
        st.dataframe(dcf_summary, use_container_width=True)
        _download_button("Download DCF CSV", dcf_summary, "dcf_summary.csv")
    with tab4:
        st.dataframe(dcf_projection, use_container_width=True)
        _download_button("Download projection CSV", dcf_projection, "dcf_projection.csv")
    with tab5:
        st.dataframe(dcf_scenarios, use_container_width=True)
        _download_button("Download DCF scenarios CSV", dcf_scenarios, "dcf_scenarios.csv")
    with tab6:
        st.dataframe(sec_filings, use_container_width=True)
        _download_button("Download SEC filings CSV", sec_filings, "sec_filings.csv")
    with tab7:
        st.dataframe(filing_reactions, use_container_width=True)
        _download_button("Download filing reactions CSV", filing_reactions, "filing_reactions.csv")
    with tab8:
        st.dataframe(sec_quarterly_fundamentals, use_container_width=True)
        _download_button("Download SEC quarterlies CSV", sec_quarterly_fundamentals, "sec_quarterlies.csv")

    st.subheader("Generated Files")
    st.markdown(
        f"""
- Excel workbook: `{output_dirs['base'] / 'ib_recruiting_dashboard.xlsx'}`
- HTML report: `{output_dirs['base'] / 'dashboard_report.html'}`
- Executive summary: `{output_dirs['base'] / 'executive_summary.md'}`
- Recruiter case study: `{output_dirs['base'] / 'recruiter_case_study.md'}`
- Charts folder: `{output_dirs['charts']}`
"""
    )
else:
    st.info("Enter a peer set and click Run Analysis to generate visuals, tables, workbook outputs, and reports.")
