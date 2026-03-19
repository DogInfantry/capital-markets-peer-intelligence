from __future__ import annotations

from pathlib import Path

from ib_showcase.analytics import (
    build_filing_event_summary,
    build_filing_reaction_table,
    build_macro_snapshot,
    build_macro_factor_correlation,
    build_performance_summary,
    build_sec_enhanced_screening_table,
    build_screening_table,
    build_transformed_macro_snapshot,
)
from ib_showcase.charts import (
    plot_correlation_heatmap,
    plot_filing_reaction_bars,
    plot_dcf_sensitivity_heatmap,
    plot_dcf_upside_bars,
    plot_macro_factor_heatmap,
    plot_macro_dashboard,
    plot_normalized_returns,
    plot_quality_value_matrix,
    plot_revenue_trends,
    plot_risk_return_scatter,
    plot_sec_quarterly_trends,
    plot_scorecard_bars,
    plot_valuation_bars,
)
from ib_showcase.config import ProjectConfig
from ib_showcase.data_fetcher import (
    fetch_company_snapshots,
    fetch_macro_series,
    fetch_price_history,
)
from ib_showcase.dcf import build_dcf_outputs
from ib_showcase.reporting import (
    ensure_output_dirs,
    save_excel_workbook,
    save_tables,
    write_case_study_report,
    write_executive_summary,
    write_html_report,
)
from ib_showcase.sec_data import fetch_sec_company_data


def run_analysis_pipeline(config: ProjectConfig, write_outputs: bool = True) -> dict[str, object]:
    prices, volumes = fetch_price_history(config)
    company_snapshots, revenue_history = fetch_company_snapshots(config.tickers)
    macro_data = fetch_macro_series(config)
    sec_entities, sec_filings, sec_snapshot, sec_quarterly_fundamentals = fetch_sec_company_data(config)

    performance_summary = build_performance_summary(
        prices=prices,
        benchmark=config.benchmark,
        risk_free_series=macro_data.get("3M Treasury Bill"),
    )
    screening_table = build_screening_table(
        performance_summary=performance_summary,
        company_snapshots=company_snapshots,
        benchmark=config.benchmark,
    )
    screening_table = build_sec_enhanced_screening_table(screening_table, sec_snapshot)
    macro_snapshot = build_macro_snapshot(macro_data)
    transformed_macro_snapshot = build_transformed_macro_snapshot(macro_data)
    macro_factor_correlation = build_macro_factor_correlation(
        prices=prices,
        macro_data=macro_data,
        benchmark=config.benchmark,
    )
    filing_reactions = build_filing_reaction_table(
        sec_filings=sec_filings,
        prices=prices,
        volumes=volumes,
        benchmark=config.benchmark,
    )
    filing_event_summary = build_filing_event_summary(filing_reactions)
    focus_ticker = screening_table.index[0] if not screening_table.empty else (config.tickers[0] if config.tickers else None)
    dcf_summary, dcf_projection, dcf_sensitivity = build_dcf_outputs(
        company_snapshots=company_snapshots,
        revenue_history=revenue_history,
        macro_snapshot=macro_snapshot,
        focus_ticker=focus_ticker,
        assumptions_file=config.assumptions_file,
    )

    outputs: dict[str, object] = {
        "prices": prices,
        "volumes": volumes,
        "company_snapshots": company_snapshots,
        "revenue_history": revenue_history,
        "macro_data": macro_data,
        "performance_summary": performance_summary,
        "screening_table": screening_table,
        "macro_snapshot": macro_snapshot,
        "transformed_macro_snapshot": transformed_macro_snapshot,
        "macro_factor_correlation": macro_factor_correlation,
        "sec_entities": sec_entities,
        "sec_filings": sec_filings,
        "sec_snapshot": sec_snapshot,
        "sec_quarterly_fundamentals": sec_quarterly_fundamentals,
        "filing_reactions": filing_reactions,
        "filing_event_summary": filing_event_summary,
        "dcf_summary": dcf_summary,
        "dcf_projection": dcf_projection,
        "dcf_sensitivity": dcf_sensitivity,
        "focus_ticker": focus_ticker,
        "chart_paths": {},
    }

    if not write_outputs:
        return outputs

    output_dirs = ensure_output_dirs(config.output_dir)
    chart_paths = {
        "normalized_returns": plot_normalized_returns(
            prices=prices,
            benchmark=config.benchmark,
            sector_label=config.sector_label,
            output_path=output_dirs["charts"] / "normalized_returns.png",
        ),
        "risk_return": plot_risk_return_scatter(
            performance_summary=performance_summary,
            benchmark=config.benchmark,
            output_path=output_dirs["charts"] / "risk_return_scatter.png",
        ),
        "valuation_bars": plot_valuation_bars(
            company_snapshots=company_snapshots,
            output_path=output_dirs["charts"] / "valuation_multiples.png",
        ),
        "quality_value": plot_quality_value_matrix(
            screening_table=screening_table,
            output_path=output_dirs["charts"] / "quality_value_matrix.png",
        ),
        "correlation_heatmap": plot_correlation_heatmap(
            prices=prices.reindex(columns=config.tickers),
            output_path=output_dirs["charts"] / "correlation_heatmap.png",
        ),
        "macro_dashboard": plot_macro_dashboard(
            macro_data=macro_data,
            output_path=output_dirs["charts"] / "macro_dashboard.png",
        ),
        "macro_factor_correlation": plot_macro_factor_heatmap(
            macro_factor_correlation=macro_factor_correlation,
            output_path=output_dirs["charts"] / "macro_factor_correlation.png",
        ),
        "revenue_trends": plot_revenue_trends(
            revenue_history=revenue_history,
            output_path=output_dirs["charts"] / "revenue_trends.png",
        ),
        "sec_quarterly_trends": plot_sec_quarterly_trends(
            sec_quarterly_fundamentals=sec_quarterly_fundamentals,
            focus_ticker=focus_ticker,
            output_path=output_dirs["charts"] / "sec_quarterly_trends.png",
        ),
        "filing_reactions": plot_filing_reaction_bars(
            filing_reactions=filing_reactions,
            focus_ticker=focus_ticker,
            output_path=output_dirs["charts"] / "filing_reactions.png",
        ),
        "scorecard_bars": plot_scorecard_bars(
            screening_table=screening_table,
            output_path=output_dirs["charts"] / "scorecard_bars.png",
        ),
        "dcf_upside": plot_dcf_upside_bars(
            dcf_summary=dcf_summary,
            output_path=output_dirs["charts"] / "dcf_upside.png",
        ),
        "dcf_sensitivity": plot_dcf_sensitivity_heatmap(
            dcf_sensitivity=dcf_sensitivity,
            focus_ticker=focus_ticker,
            output_path=output_dirs["charts"] / "dcf_sensitivity.png",
        ),
    }

    save_tables(
        tables={
            "prices": prices,
            "volumes": volumes,
            "company_snapshots": company_snapshots,
            "performance_summary": performance_summary,
            "screening_table": screening_table,
            "macro_data": macro_data,
            "macro_snapshot": macro_snapshot,
            "transformed_macro_snapshot": transformed_macro_snapshot,
            "macro_factor_correlation": macro_factor_correlation,
            "revenue_history": revenue_history,
            "sec_entities": sec_entities,
            "sec_filings": sec_filings,
            "sec_snapshot": sec_snapshot,
            "sec_quarterly_fundamentals": sec_quarterly_fundamentals,
            "filing_reactions": filing_reactions,
            "filing_event_summary": filing_event_summary,
            "dcf_summary": dcf_summary,
            "dcf_projection": dcf_projection,
            "dcf_sensitivity": dcf_sensitivity,
        },
        table_dir=output_dirs["tables"],
    )

    save_excel_workbook(
        output_path=output_dirs["base"] / "ib_recruiting_dashboard.xlsx",
        tables={
            "Performance Summary": performance_summary,
            "Company Snapshots": company_snapshots,
            "Screening Table": screening_table,
            "Macro Snapshot": macro_snapshot,
            "Macro Transform": transformed_macro_snapshot,
            "Macro Corr": macro_factor_correlation,
            "Revenue History": revenue_history,
            "SEC Snapshot": sec_snapshot,
            "SEC Filings": sec_filings,
            "SEC Quarterlies": sec_quarterly_fundamentals,
            "Filing Reactions": filing_reactions,
            "Event Summary": filing_event_summary,
            "DCF Summary": dcf_summary,
            "DCF Projection": dcf_projection,
            "DCF Sensitivity": dcf_sensitivity,
        },
    )

    write_executive_summary(
        config=config,
        performance_summary=performance_summary,
        company_snapshots=company_snapshots,
        screening_table=screening_table,
        macro_snapshot=transformed_macro_snapshot,
        filing_event_summary=filing_event_summary,
        filing_reactions=filing_reactions,
        sec_snapshot=sec_snapshot,
        dcf_summary=dcf_summary,
        chart_paths=chart_paths,
        output_path=output_dirs["base"] / "executive_summary.md",
    )
    write_html_report(
        config=config,
        screening_table=screening_table,
        performance_summary=performance_summary,
        macro_snapshot=transformed_macro_snapshot,
        sec_snapshot=sec_snapshot,
        filing_event_summary=filing_event_summary,
        dcf_summary=dcf_summary,
        chart_paths=chart_paths,
        output_path=output_dirs["base"] / "dashboard_report.html",
    )
    write_case_study_report(
        config=config,
        focus_ticker=focus_ticker,
        screening_table=screening_table,
        sec_snapshot=sec_snapshot,
        filing_reactions=filing_reactions,
        dcf_summary=dcf_summary,
        macro_snapshot=transformed_macro_snapshot,
        output_path=output_dirs["base"] / "recruiter_case_study.md",
    )

    outputs["output_dirs"] = output_dirs
    outputs["chart_paths"] = chart_paths
    return outputs
