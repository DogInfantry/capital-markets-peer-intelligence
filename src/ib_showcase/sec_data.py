from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from ib_showcase.config import ProjectConfig


SEC_BASE_URL = "https://data.sec.gov"
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"


def _cache_path(cache_dir: Path, key: str) -> Path:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"


def _get_json(url: str, headers: dict[str, str], cache_dir: Path) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(cache_dir, url)
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _coalesce_company_fact(
    facts_data: dict[str, Any],
    taxonomy: str,
    concepts: list[str],
    unit_preferences: list[str],
    forms: set[str] | None = None,
) -> pd.DataFrame:
    taxonomy_data = facts_data.get("facts", {}).get(taxonomy, {})
    for concept in concepts:
        concept_data = taxonomy_data.get(concept, {})
        units = concept_data.get("units", {})
        for unit in unit_preferences:
            if unit not in units:
                continue
            frame = pd.DataFrame(units[unit])
            if frame.empty:
                continue
            if forms:
                frame = frame[frame["form"].isin(forms)]
            if frame.empty:
                continue
            frame["end"] = pd.to_datetime(frame["end"], errors="coerce")
            frame["filed"] = pd.to_datetime(frame["filed"], errors="coerce")
            frame["taxonomy"] = taxonomy
            frame["concept"] = concept
            frame["unit"] = unit
            return frame.sort_values(["end", "filed"])
    return pd.DataFrame()


def _latest_fact_value(frame: pd.DataFrame) -> float | None:
    if frame.empty or "val" not in frame.columns:
        return None
    clean = frame.dropna(subset=["val"])
    if clean.empty:
        return None
    return float(clean.iloc[-1]["val"])


def _latest_fact_date(frame: pd.DataFrame) -> pd.Timestamp | None:
    if frame.empty or "filed" not in frame.columns:
        return None
    clean = frame.dropna(subset=["filed"])
    if clean.empty:
        return None
    return pd.Timestamp(clean.iloc[-1]["filed"])


def _fact_columns(frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
    expected_columns = ["end", "filed", "form", "fy", "fp", "frame", "val"]
    if frame.empty:
        return pd.DataFrame(columns=["end", "filed", "form", "fy", "fp", "frame", value_name])
    prepared = frame.copy()
    for column in expected_columns:
        if column not in prepared.columns:
            prepared[column] = pd.NA
    return prepared[expected_columns].rename(columns={"val": value_name})


def _build_quarterly_fundamentals(
    ticker: str,
    facts_data: dict[str, Any],
) -> pd.DataFrame:
    revenue = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="us-gaap",
        concepts=["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        unit_preferences=["USD"],
        forms={"10-Q", "10-K", "20-F", "6-K"},
    )
    net_income = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="us-gaap",
        concepts=["NetIncomeLoss"],
        unit_preferences=["USD"],
        forms={"10-Q", "10-K", "20-F", "6-K"},
    )

    if revenue.empty and net_income.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "end",
                "filed",
                "form",
                "fy",
                "fp",
                "revenue",
                "net_income",
            ]
        )

    merged = pd.merge(
        _fact_columns(revenue, "revenue"),
        _fact_columns(net_income, "net_income"),
        on=["end", "filed", "form", "fy", "fp", "frame"],
        how="outer",
    )
    merged["ticker"] = ticker
    merged = merged.sort_values(["end", "filed"]).drop_duplicates(
        subset=["end", "form", "fy", "fp"], keep="last"
    )
    return merged[
        ["ticker", "end", "filed", "form", "fy", "fp", "revenue", "net_income"]
    ]


def _build_sec_snapshot_row(
    ticker: str,
    ticker_meta: dict[str, Any],
    filings: pd.DataFrame,
    facts_data: dict[str, Any],
) -> dict[str, Any]:
    annual_forms = {"10-K", "20-F", "40-F"}
    quarterly_forms = {"10-Q", "6-K"}

    revenue = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="us-gaap",
        concepts=["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        unit_preferences=["USD"],
        forms=annual_forms | quarterly_forms,
    )
    net_income = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="us-gaap",
        concepts=["NetIncomeLoss"],
        unit_preferences=["USD"],
        forms=annual_forms | quarterly_forms,
    )
    assets = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="us-gaap",
        concepts=["Assets"],
        unit_preferences=["USD"],
        forms=annual_forms | quarterly_forms,
    )
    liabilities = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="us-gaap",
        concepts=["Liabilities"],
        unit_preferences=["USD"],
        forms=annual_forms | quarterly_forms,
    )
    equity = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="us-gaap",
        concepts=["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        unit_preferences=["USD"],
        forms=annual_forms | quarterly_forms,
    )
    cash = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="us-gaap",
        concepts=["CashAndCashEquivalentsAtCarryingValue"],
        unit_preferences=["USD"],
        forms=annual_forms | quarterly_forms,
    )
    shares = _coalesce_company_fact(
        facts_data=facts_data,
        taxonomy="dei",
        concepts=["EntityCommonStockSharesOutstanding"],
        unit_preferences=["shares"],
        forms=annual_forms | quarterly_forms,
    )

    latest_10q = filings.loc[filings["form"] == "10-Q", "filing_date"].max() if not filings.empty else pd.NaT
    latest_10k = filings.loc[filings["form"].isin(["10-K", "20-F", "40-F"]), "filing_date"].max() if not filings.empty else pd.NaT
    latest_8k = filings.loc[filings["form"].str.startswith("8-K"), "filing_date"].max() if not filings.empty else pd.NaT

    snapshot_row = {
        "ticker": ticker,
        "sec_company_name": ticker_meta.get("title", ticker),
        "cik": str(ticker_meta.get("cik_str", "")).zfill(10),
        "latest_sec_revenue": _latest_fact_value(revenue),
        "latest_sec_net_income": _latest_fact_value(net_income),
        "latest_sec_assets": _latest_fact_value(assets),
        "latest_sec_liabilities": _latest_fact_value(liabilities),
        "latest_sec_equity": _latest_fact_value(equity),
        "latest_sec_cash": _latest_fact_value(cash),
        "latest_sec_shares": _latest_fact_value(shares),
        "latest_sec_revenue_filed": _latest_fact_date(revenue),
        "latest_sec_net_income_filed": _latest_fact_date(net_income),
        "last_10q_filed": latest_10q,
        "last_10k_filed": latest_10k,
        "last_8k_filed": latest_8k,
        "interesting_filings_last_12m": int(
            filings.loc[
                filings["filing_date"] >= (pd.Timestamp.today().normalize() - pd.Timedelta(days=365))
            ].shape[0]
        )
        if not filings.empty
        else 0,
    }

    if snapshot_row["latest_sec_equity"] not in (None, 0) and snapshot_row["latest_sec_net_income"] is not None:
        snapshot_row["sec_roe_pct"] = (
            snapshot_row["latest_sec_net_income"] / snapshot_row["latest_sec_equity"] * 100
        )
    else:
        snapshot_row["sec_roe_pct"] = None

    if snapshot_row["latest_sec_assets"] not in (None, 0) and snapshot_row["latest_sec_liabilities"] is not None:
        snapshot_row["sec_liabilities_to_assets_pct"] = (
            snapshot_row["latest_sec_liabilities"] / snapshot_row["latest_sec_assets"] * 100
        )
    else:
        snapshot_row["sec_liabilities_to_assets_pct"] = None

    return snapshot_row


def fetch_sec_company_data(
    config: ProjectConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cache_dir = config.output_dir / ".sec_cache"
    headers = {
        "User-Agent": config.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.sec.gov/",
        "Host": "data.sec.gov",
    }
    ticker_headers = {
        "User-Agent": config.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.sec.gov/",
    }

    ticker_map_payload = _get_json(SEC_TICKER_URL, ticker_headers, cache_dir)
    ticker_map = pd.DataFrame(ticker_map_payload).T
    ticker_map["ticker"] = ticker_map["ticker"].str.upper()
    ticker_map = ticker_map.set_index("ticker")

    sec_entities: list[dict[str, Any]] = []
    sec_filings_frames: list[pd.DataFrame] = []
    sec_snapshot_rows: list[dict[str, Any]] = []
    sec_quarterly_frames: list[pd.DataFrame] = []

    for ticker in config.tickers:
        if ticker not in ticker_map.index:
            sec_entities.append({"ticker": ticker, "cik": None, "sec_company_name": ticker})
            continue

        ticker_meta = ticker_map.loc[ticker].to_dict()
        cik = str(int(ticker_meta["cik_str"])).zfill(10)
        sec_entities.append(
            {
                "ticker": ticker,
                "cik": cik,
                "sec_company_name": ticker_meta.get("title", ticker),
            }
        )

        submissions_url = f"{SEC_BASE_URL}/submissions/CIK{cik}.json"
        companyfacts_url = f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"

        submissions_payload = _get_json(submissions_url, headers, cache_dir)
        companyfacts_payload = _get_json(companyfacts_url, headers, cache_dir)

        recent = submissions_payload.get("filings", {}).get("recent", {})
        filings = pd.DataFrame(recent)
        if not filings.empty:
            filings = filings.rename(
                columns={
                    "filingDate": "filing_date",
                    "acceptanceDateTime": "acceptance_datetime",
                    "primaryDocument": "primary_document",
                    "primaryDocDescription": "primary_doc_description",
                    "accessionNumber": "accession_number",
                }
            )
            filings["ticker"] = ticker
            filings["cik"] = cik
            filings["filing_date"] = pd.to_datetime(filings["filing_date"], errors="coerce")
            filings["acceptance_datetime"] = pd.to_datetime(
                filings["acceptance_datetime"], errors="coerce", utc=True
            )
            filings["accession_path"] = filings["accession_number"].str.replace("-", "", regex=False)
            filings["filing_url"] = (
                "https://www.sec.gov/Archives/edgar/data/"
                + filings["cik"].astype(str).str.lstrip("0")
                + "/"
                + filings["accession_path"].fillna("")
                + "/"
                + filings["primary_document"].fillna("")
            )
            interesting_forms = filings["form"].astype(str).str.contains(
                r"^(?:10-K|10-Q|8-K|20-F|40-F|6-K|S-1|S-3|424B|FWP|DEF 14A)",
                regex=True,
            )
            filings = filings.loc[interesting_forms].copy()
            filings = filings.sort_values("filing_date", ascending=False)
            sec_filings_frames.append(filings)

        snapshot_row = _build_sec_snapshot_row(
            ticker=ticker,
            ticker_meta=ticker_meta,
            filings=filings if not filings.empty else pd.DataFrame(),
            facts_data=companyfacts_payload,
        )
        sec_snapshot_rows.append(snapshot_row)

        quarterly_fundamentals = _build_quarterly_fundamentals(
            ticker=ticker, facts_data=companyfacts_payload
        )
        if not quarterly_fundamentals.empty:
            sec_quarterly_frames.append(quarterly_fundamentals)

    sec_entities_df = pd.DataFrame(sec_entities).set_index("ticker") if sec_entities else pd.DataFrame()
    sec_filings_df = (
        pd.concat(sec_filings_frames, ignore_index=True).sort_values(["ticker", "filing_date"], ascending=[True, False])
        if sec_filings_frames
        else pd.DataFrame()
    )
    sec_snapshot_df = (
        pd.DataFrame(sec_snapshot_rows).set_index("ticker").sort_index()
        if sec_snapshot_rows
        else pd.DataFrame()
    )
    sec_quarterly_df = (
        pd.concat([frame for frame in sec_quarterly_frames if not frame.empty], ignore_index=True).sort_values(["ticker", "end", "filed"])
        if [frame for frame in sec_quarterly_frames if not frame.empty]
        else pd.DataFrame()
    )

    return sec_entities_df, sec_filings_df, sec_snapshot_df, sec_quarterly_df
