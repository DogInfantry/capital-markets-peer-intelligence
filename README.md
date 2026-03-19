# Capital Markets Peer Intelligence

This repository is a recruiter-facing finance analytics project designed for an MBA candidate targeting investment banking, capital markets, corporate finance, and strategic finance roles. It combines market data, SEC filings, macro context, peer benchmarking, and valuation outputs into a workflow that looks and feels like a real coverage or issuer-intelligence work product.

## What This Project Does

- Tracks a selected peer group using free market, macro, and SEC data
- Highlights what changed in recent filings and how markets reacted
- Compares companies on performance, quality, value, and defensiveness
- Produces an explainable valuation layer with sensitivity and scenario views
- Generates visual and written outputs that are easy for recruiters and hiring managers to review

## Why It Works As A Recruiting Project

- It is business-first, not code-first
- It shows structured thinking, not just chart-making
- It uses official SEC and FRED data sources alongside market data
- It creates visible deliverables instead of staying inside notebooks or scripts
- It is detailed enough to stand out, but simple enough to explain clearly in interviews

## Deliverables At A Glance

After one run, the project produces:

- a chart pack in `outputs/charts/`
- an Excel workbook in `outputs/ib_recruiting_dashboard.xlsx`
- a browser-ready report in `outputs/dashboard_report.html`
- an executive summary in `outputs/executive_summary.md`
- a recruiter-style case study in `outputs/recruiter_case_study.md`
- a curated GitHub-friendly showcase in `sample_outputs/`

## What This Demonstrates

- Market data ingestion with free APIs
- SEC filing and company-facts analysis
- Peer benchmarking and comps-style analysis
- Macro overlay using Federal Reserve Economic Data (FRED)
- Automated chart generation for bar charts, trend lines, heatmaps, and event visuals
- Intrinsic valuation with DCF sensitivity and simple sector-based scenarios
- Interactive Streamlit dashboard for self-serve walkthroughs
- Clean, modular, Git-ready Python structure

## Free data sources used

- `yfinance` for equity prices and company snapshot fields
- Official SEC EDGAR `submissions` and `companyfacts` JSON endpoints for filings and standardized XBRL fundamentals
- `pandas-datareader` for FRED macro series
- `matplotlib` and `seaborn` for professional charts
- `plotly` and `streamlit` for interactive dashboards
- `pandas` and `numpy` for analytics
- `XlsxWriter` for Excel deliverables

No paid terminals, no proprietary APIs, and no subscription datasets are required.

## Outputs

Running the project creates:

- CSV tables in `outputs/tables/`
- PNG charts in `outputs/charts/`
- An Excel workbook in `outputs/`
- A recruiter-readable markdown memo in `outputs/executive_summary.md`
- A polished HTML report in `outputs/dashboard_report.html`
- A case-study style memo in `outputs/recruiter_case_study.md`
- SEC filing history, filing-reaction, and company-facts tables in `outputs/tables/`

## GitHub portfolio structure

For GitHub, the cleanest setup is:

- Source code and app files in the repo root and `src/`
- Generated working files in `outputs/` kept out of version control
- A curated `sample_outputs/` folder committed to GitHub for recruiters to browse

Recommended recruiter-facing files to keep in GitHub:

- `sample_outputs/dashboard_report.html`
- `sample_outputs/executive_summary.md`
- `sample_outputs/recruiter_case_study.md`
- `sample_outputs/charts/` with a small chart pack

This keeps the repository polished while still showing visible deliverables.

## Example use cases

Tech comps example:

```bash
python run_analysis.py --tickers NVDA AMD AVGO QCOM TSM --benchmark SOXX --sector-label "AI Semiconductor Peer Set"
```

Banking comps example:

```bash
python run_analysis.py --tickers JPM GS MS BAC C --benchmark XLF --sector-label "US Money Center and Investment Banks"
```

Advisory / capital markets example:

```bash
python run_analysis.py --tickers GS MS JEF LAZ PJT --benchmark ^GSPC --sector-label "Advisory and Capital Markets Peer Set"
```

With manual DCF overrides:

```bash
python run_analysis.py --tickers GS MS JEF LAZ PJT --benchmark ^GSPC --sector-label "Advisory and Capital Markets Peer Set" --assumptions-file templates/dcf_assumptions_template.csv
```

The model also generates sector-based `Bear`, `Base`, and `Bull` DCF cases automatically using simple assumption shifts around growth, margin, and WACC.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_analysis.py
```

Launch the interactive dashboard:

```bash
streamlit run streamlit_app.py
```

## Important modeling note

The DCF layer is intended as a portfolio-quality demonstration of valuation logic and sensitivity analysis. For banks and diversified financials, relative valuation and return metrics are often more decision-relevant than a classic enterprise DCF, so use the DCF output as a discussion tool rather than a definitive fair-value view.

If `python` is not on your PATH in Windows, try:

```bash
py -m venv .venv
py -m pip install -r requirements.txt
py run_analysis.py
```

## Why hiring managers care

This repo shows more than coding. It shows:

- You can source and clean external data
- You can work with official SEC filing data, not just convenience market APIs
- You can frame an investment or industry story
- You understand benchmarking, valuation, and macro context
- You can produce both relative valuation and intrinsic valuation outputs
- You can package analysis into decision-ready outputs
- You can build a repeatable workflow that belongs in GitHub

## What you can show without opening code

After one run, you can open and present:

- `outputs/charts/` for standalone visuals
- `outputs/ib_recruiting_dashboard.xlsx` for spreadsheet-style analysis
- `outputs/dashboard_report.html` for a polished visual report in a browser
- `outputs/recruiter_case_study.md` for a concise recruiter-facing writeup
- `streamlit_app.py` for a live interactive walkthrough
- `sample_outputs/` in GitHub for a stable public showcase

## Good talking points in interviews

- Why you chose the peer set
- Which multiples matter and where they break down
- How macro conditions influence sector valuation
- How DCF assumptions change implied value
- How filing dates and disclosure events move stock prices
- How SEC facts change the story relative to high-level snapshot data
- How you handled missing data and inconsistent company disclosures
- How you would extend the project with DCF, transaction comps, or Power BI / Streamlit

## Suggested next upgrades

- Add transaction comps from manually curated deal files
- Publish the Streamlit app to the cloud
- Schedule automatic weekly refreshes
- Add regression-based factor attribution
