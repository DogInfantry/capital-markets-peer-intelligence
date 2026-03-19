from __future__ import annotations

from pathlib import Path

import pandas as pd

from ib_showcase.config import ProjectConfig


def ensure_output_dirs(base_dir: Path) -> dict[str, Path]:
    chart_dir = base_dir / "charts"
    table_dir = base_dir / "tables"
    chart_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    return {"base": base_dir, "charts": chart_dir, "tables": table_dir}


def save_tables(tables: dict[str, pd.DataFrame], table_dir: Path) -> None:
    table_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(table_dir / f"{name}.csv")


def save_excel_workbook(output_path: Path, tables: dict[str, pd.DataFrame]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#D9EAF7", "border": 1}
        )
        number_format = workbook.add_format({"num_format": "#,##0.00"})

        for sheet_name, table in tables.items():
            clean_name = sheet_name[:31]
            export_table = table.reset_index()
            for column_name in export_table.select_dtypes(include=["datetimetz"]).columns:
                export_table[column_name] = export_table[column_name].dt.tz_localize(None)
            export_table.to_excel(writer, sheet_name=clean_name, index=False)
            worksheet = writer.sheets[clean_name]

            for column_index, column_name in enumerate(export_table.columns):
                worksheet.write(0, column_index, column_name, header_format)
                width = max(len(column_name) + 2, 14)
                cell_format = (
                    number_format
                    if pd.api.types.is_numeric_dtype(export_table[column_name])
                    else None
                )
                worksheet.set_column(column_index, column_index, width, cell_format)


def _fmt_number(value: float | int | None, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:,.2f}{suffix}"


def _table_to_html(table: pd.DataFrame, max_rows: int = 10) -> str:
    if table.empty:
        return "<p>Data unavailable.</p>"
    return table.head(max_rows).to_html(classes="data-table", border=0)


def write_executive_summary(
    config: ProjectConfig,
    performance_summary: pd.DataFrame,
    company_snapshots: pd.DataFrame,
    screening_table: pd.DataFrame,
    macro_snapshot: pd.DataFrame,
    filing_event_summary: pd.DataFrame,
    filing_reactions: pd.DataFrame,
    sec_snapshot: pd.DataFrame,
    dcf_summary: pd.DataFrame,
    focus_scenarios: pd.DataFrame,
    chart_paths: dict[str, Path],
    output_path: Path,
) -> None:
    top_performer = performance_summary.drop(index=config.benchmark, errors="ignore").head(1)
    highest_quality = screening_table.sort_values("quality_score", ascending=False).head(1)
    best_value = screening_table.sort_values("value_score", ascending=False).head(1)
    strongest_composite = screening_table.head(1)
    best_dcf = dcf_summary.head(1) if not dcf_summary.empty else pd.DataFrame()
    strongest_filing_signal = filing_event_summary.head(1) if not filing_event_summary.empty else pd.DataFrame()

    macro_lines: list[str] = []
    for series_name, row in macro_snapshot.head(4).iterrows():
        macro_lines.append(
            f"- **{series_name}**: latest {_fmt_number(row['latest'])}, 30-day change {_fmt_number(row['change_30d'])}, 1-year change {_fmt_number(row['change_1y'])} ({row.get('display_unit', 'level')})"
        )

    top_performer_text = "n/a"
    if not top_performer.empty:
        ticker = top_performer.index[0]
        top_performer_text = (
            f"{ticker} with total return {_fmt_number(top_performer.iloc[0]['total_return_pct'], '%')} "
            f"and annualized return {_fmt_number(top_performer.iloc[0]['annualized_return_pct'], '%')}."
        )

    highest_quality_text = "n/a"
    if not highest_quality.empty:
        ticker = highest_quality.index[0]
        highest_quality_text = (
            f"{ticker} leads on quality score at {_fmt_number(highest_quality.iloc[0]['quality_score'])}, "
            f"supported by ROE {_fmt_number(highest_quality.iloc[0].get('roe_pct'), '%')} "
            f"and operating margin {_fmt_number(highest_quality.iloc[0].get('operating_margin_pct'), '%')}."
        )

    best_value_text = "n/a"
    if not best_value.empty:
        ticker = best_value.index[0]
        best_value_text = (
            f"{ticker} screens best on value score at {_fmt_number(best_value.iloc[0]['value_score'])}, "
            f"with trailing P/E {_fmt_number(best_value.iloc[0].get('trailing_pe'))} "
            f"and price/book {_fmt_number(best_value.iloc[0].get('price_to_book'))}."
        )

    strongest_composite_text = "n/a"
    if not strongest_composite.empty:
        ticker = strongest_composite.index[0]
        strongest_composite_text = (
            f"{ticker} ranks first on the blended score at {_fmt_number(strongest_composite.iloc[0]['composite_score'])}."
        )

    best_dcf_text = "n/a"
    if not best_dcf.empty:
        ticker = best_dcf.index[0]
        best_dcf_text = (
            f"{ticker} shows implied value of {_fmt_number(best_dcf.iloc[0]['implied_share_price'])} per share "
            f"versus current price {_fmt_number(best_dcf.iloc[0]['current_price'])}, "
            f"or {_fmt_number(best_dcf.iloc[0]['upside_downside_pct'], '%')} upside/downside."
        )

    scenario_text = "n/a"
    if not focus_scenarios.empty:
        ordered = (
            focus_scenarios.set_index("case")
            if "case" in focus_scenarios.columns
            else pd.DataFrame()
        )
        if not ordered.empty and {"Bear", "Base", "Bull"}.intersection(set(ordered.index)):
            bear = ordered.loc["Bear", "implied_share_price"] if "Bear" in ordered.index else None
            base = ordered.loc["Base", "implied_share_price"] if "Base" in ordered.index else None
            bull = ordered.loc["Bull", "implied_share_price"] if "Bull" in ordered.index else None
            scenario_text = (
                f"Focus-name scenario range runs from {_fmt_number(bear)} in Bear, "
                f"to {_fmt_number(base)} in Base, to {_fmt_number(bull)} in Bull."
            )

    filing_signal_text = "n/a"
    if not strongest_filing_signal.empty:
        form = strongest_filing_signal.index[0]
        filing_signal_text = (
            f"{form} filings drove the largest average absolute day-0 excess move at "
            f"{_fmt_number(strongest_filing_signal.iloc[0]['avg_abs_excess_day0_pct'], '%')}, "
            f"with average volume {_fmt_number(strongest_filing_signal.iloc[0]['avg_volume_ratio'])}x trailing 20-day volume."
        )

    filing_recency_text = "n/a"
    if not sec_snapshot.empty and "last_10q_filed" in sec_snapshot.columns:
        recent_10q = sec_snapshot["last_10q_filed"].dropna()
        if not recent_10q.empty:
            most_recent_ticker = recent_10q.sort_values(ascending=False).index[0]
            filing_recency_text = (
                f"{most_recent_ticker} filed the most recent 10-Q on {pd.Timestamp(recent_10q.loc[most_recent_ticker]).date()}."
            )

    summary = f"""# {config.sector_label}

## Project framing

This memo was generated by a Python workflow designed to showcase investment-banking style analysis using only free data sources. It combines market performance, valuation screening, operating quality, macro context, and DCF output in a format that is easy for a recruiter or hiring manager to scan.

## Key takeaways

- Top market performer: {top_performer_text}
- Highest quality profile: {highest_quality_text}
- Best value screen: {best_value_text}
- Highest composite ranking: {strongest_composite_text}
- Most attractive DCF setup: {best_dcf_text}
- Sector scenario range: {scenario_text}
- Filing-event signal: {filing_signal_text}
- Filing recency: {filing_recency_text}

## Macro backdrop

{chr(10).join(macro_lines) if macro_lines else "- Macro data unavailable"}

## Deliverables created

- Price, macro, comps, and DCF datasets as CSV files
- Chart pack in `{config.output_dir.as_posix()}/charts/`
- Excel workbook: `ib_recruiting_dashboard.xlsx`
- HTML report: `dashboard_report.html`
- Case-study style memo: `recruiter_case_study.md`

## Charts included

{chr(10).join(f"- {name}: `{path.name}`" for name, path in chart_paths.items())}

## How to present this in interviews

- Explain why this peer set matters strategically
- Discuss which multiples are most relevant for this sector
- Highlight what the macro setup implies for valuation and capital markets activity
- Walk through how you balanced momentum, quality, value, and defensiveness in the ranking model
- Use the DCF output to explain judgment, assumptions, and sensitivity analysis
- Use the Bear / Base / Bull sector cases to show how assumptions change valuation without overcomplicating the model
- Use SEC filing reactions to explain what changed, when the market noticed, and how management disclosure affected perception
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")


def write_html_report(
    config: ProjectConfig,
    screening_table: pd.DataFrame,
    performance_summary: pd.DataFrame,
    macro_snapshot: pd.DataFrame,
    sec_snapshot: pd.DataFrame,
    filing_event_summary: pd.DataFrame,
    dcf_summary: pd.DataFrame,
    focus_scenarios: pd.DataFrame,
    chart_paths: dict[str, Path],
    output_path: Path,
) -> None:
    focus_ticker = screening_table.index[0] if not screening_table.empty else "n/a"
    dcf_focus = dcf_summary.loc[[focus_ticker]] if focus_ticker in dcf_summary.index else dcf_summary.head(1)
    relative_chart_paths = {
        name: path.relative_to(output_path.parent).as_posix() if path.is_relative_to(output_path.parent) else path.as_posix()
        for name, path in chart_paths.items()
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{config.sector_label} Dashboard Report</title>
  <style>
    body {{
      font-family: Georgia, "Times New Roman", serif;
      margin: 0;
      background: linear-gradient(180deg, #f4f0e8 0%, #ffffff 30%);
      color: #172033;
    }}
    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 40px 28px 60px;
    }}
    .hero {{
      background: #172033;
      color: #f7f5ef;
      padding: 28px;
      border-radius: 18px;
      margin-bottom: 28px;
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: 34px;
    }}
    .hero p {{
      margin: 0;
      max-width: 760px;
      line-height: 1.5;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 18px;
      margin-bottom: 28px;
    }}
    .card {{
      background: white;
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 10px 30px rgba(23, 32, 51, 0.08);
    }}
    .card h2 {{
      margin-top: 0;
      font-size: 18px;
    }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px;
      margin: 24px 0;
    }}
    .chart-grid img {{
      width: 100%;
      border-radius: 14px;
      border: 1px solid #e6e0d5;
      background: white;
    }}
    .data-table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 14px;
    }}
    .data-table th, .data-table td {{
      border-bottom: 1px solid #ece8df;
      padding: 8px 10px;
      text-align: left;
    }}
    .section-title {{
      margin: 30px 0 14px;
      font-size: 24px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>{config.sector_label}</h1>
      <p>Automated Python report combining free market data, free macro data, peer benchmarking, DCF valuation, and visual storytelling. Built to be reviewable by recruiters, managers, and interviewers without paid data subscriptions.</p>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Focus Ticker</h2>
        <p>{focus_ticker}</p>
      </div>
      <div class="card">
        <h2>Top Ranked Peer</h2>
        <p>{screening_table.index[0] if not screening_table.empty else "n/a"}</p>
      </div>
      <div class="card">
        <h2>Best DCF Name</h2>
        <p>{dcf_summary.index[0] if not dcf_summary.empty else "n/a"}</p>
      </div>
      <div class="card">
        <h2>Benchmark</h2>
        <p>{config.benchmark}</p>
      </div>
    </section>

    <h2 class="section-title">Chart Pack</h2>
    <section class="chart-grid">
      {''.join(f'<div class="card"><h2>{name.replace("_", " ").title()}</h2><img src="{path}" alt="{name}"></div>' for name, path in relative_chart_paths.items())}
    </section>

    <h2 class="section-title">Screening Table</h2>
    <section class="card">
      {_table_to_html(screening_table)}
    </section>

    <h2 class="section-title">Performance Summary</h2>
    <section class="card">
      {_table_to_html(performance_summary)}
    </section>

    <h2 class="section-title">DCF Summary</h2>
    <section class="card">
      {_table_to_html(dcf_summary)}
    </section>

    <h2 class="section-title">Focus Scenarios</h2>
    <section class="card">
      {_table_to_html(focus_scenarios)}
    </section>

    <h2 class="section-title">Macro Snapshot</h2>
    <section class="card">
      {_table_to_html(macro_snapshot)}
    </section>

    <h2 class="section-title">SEC Snapshot</h2>
    <section class="card">
      {_table_to_html(sec_snapshot)}
    </section>

    <h2 class="section-title">Filing Event Summary</h2>
    <section class="card">
      {_table_to_html(filing_event_summary)}
    </section>

    <h2 class="section-title">Interview Framing</h2>
    <section class="card">
      <p>Use this report to explain peer selection, valuation tradeoffs, macro sensitivity, and the judgment embedded in a DCF model. A strong interview walkthrough starts with business context, then links relative valuation to intrinsic value and market conditions.</p>
      <p>The name to highlight from a value-creation perspective is {dcf_focus.index[0] if not dcf_focus.empty else "n/a"}, based on the current output set.</p>
    </section>
  </div>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def write_case_study_report(
    config: ProjectConfig,
    focus_ticker: str | None,
    screening_table: pd.DataFrame,
    sec_snapshot: pd.DataFrame,
    filing_reactions: pd.DataFrame,
    dcf_summary: pd.DataFrame,
    focus_scenarios: pd.DataFrame,
    macro_snapshot: pd.DataFrame,
    output_path: Path,
) -> None:
    selected_ticker = focus_ticker if focus_ticker in screening_table.index else (screening_table.index[0] if not screening_table.empty else "n/a")
    screening_row = screening_table.loc[selected_ticker] if selected_ticker in screening_table.index else pd.Series(dtype="object")
    sec_row = sec_snapshot.loc[selected_ticker] if selected_ticker in sec_snapshot.index else pd.Series(dtype="object")
    dcf_row = dcf_summary.loc[selected_ticker] if selected_ticker in dcf_summary.index else pd.Series(dtype="object")
    scenario_rows = (
        focus_scenarios.copy().set_index("case")
        if not focus_scenarios.empty and "case" in focus_scenarios.columns
        else pd.DataFrame()
    )
    filing_row = (
        filing_reactions.loc[filing_reactions["ticker"] == selected_ticker].sort_values("filing_date", ascending=False).head(1)
        if not filing_reactions.empty
        else pd.DataFrame()
    )
    macro_lines = []
    for series_name, row in macro_snapshot.head(3).iterrows():
        macro_lines.append(
            f"- {series_name}: latest {_fmt_number(row['latest'])}, 1-year change {_fmt_number(row['change_1y'])} ({row.get('display_unit', 'level')})"
        )

    filing_lines = "- Recent filing reaction unavailable"
    if not filing_row.empty:
        filing_lines = (
            f"- Most recent tracked filing: {filing_row.iloc[0]['form']} on {pd.Timestamp(filing_row.iloc[0]['filing_date']).date()}\n"
            f"- Day-0 excess return: {_fmt_number(filing_row.iloc[0]['excess_return_day0_pct'], '%')}\n"
            f"- 3-day excess return: {_fmt_number(filing_row.iloc[0]['excess_return_3d_pct'], '%')}\n"
            f"- Volume vs 20-day average: {_fmt_number(filing_row.iloc[0]['volume_ratio_vs_20d'])}x"
        )

    scenario_lines = "- Sector scenario cases unavailable"
    if not scenario_rows.empty:
        scenario_lines = (
            f"- Bear implied value: {_fmt_number(scenario_rows.loc['Bear', 'implied_share_price']) if 'Bear' in scenario_rows.index else 'n/a'}\n"
            f"- Base implied value: {_fmt_number(scenario_rows.loc['Base', 'implied_share_price']) if 'Base' in scenario_rows.index else 'n/a'}\n"
            f"- Bull implied value: {_fmt_number(scenario_rows.loc['Bull', 'implied_share_price']) if 'Bull' in scenario_rows.index else 'n/a'}"
        )

    report = f"""# Recruiter Case Study: {selected_ticker}

## Situation

This project evaluates {config.sector_label} using free market, fundamental, and macro data. The objective is to identify which peer best combines business quality, valuation attractiveness, and resilience in the current market environment.

## What I built

- Automated peer-data ingestion from Yahoo Finance
- Macro backdrop overlay using FRED
- Scored peer-screening model for momentum, quality, value, and defensiveness
- DCF valuation layer with sensitivity analysis
- Reusable output pack across charts, tables, Excel, markdown, and HTML

## Focus company

- Ticker: {selected_ticker}
- Composite score: {_fmt_number(screening_row.get('composite_score'))}
- Quality score: {_fmt_number(screening_row.get('quality_score'))}
- Value score: {_fmt_number(screening_row.get('value_score'))}
- Latest SEC revenue: {_fmt_number(sec_row.get('latest_sec_revenue'))}
- Latest SEC net income: {_fmt_number(sec_row.get('latest_sec_net_income'))}
- Last 10-Q filed: {pd.Timestamp(sec_row.get('last_10q_filed')).date() if pd.notna(sec_row.get('last_10q_filed')) else 'n/a'}
- DCF implied share price: {_fmt_number(dcf_row.get('implied_share_price'))}
- DCF upside/downside: {_fmt_number(dcf_row.get('upside_downside_pct'), '%')}

## Macro context

{chr(10).join(macro_lines) if macro_lines else "- Macro data unavailable"}

## Filing reaction context

{filing_lines}

## Sector scenario context

{scenario_lines}

## Why this matters

The project demonstrates analytical structuring, business framing, valuation thinking, and communication quality. It is designed to resemble the kind of work product that can support networking conversations, interview discussions, and take-home recruiting assignments.

## How I would extend it

- Add transaction comps from curated deal data
- Add scenario-based DCF assumptions by sector
- Publish this as a Streamlit web app for live walkthroughs
- Add PowerPoint-ready exports for formal recruiting packets
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
