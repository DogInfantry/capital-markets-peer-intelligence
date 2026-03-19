from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ProjectConfig:
    tickers: list[str]
    benchmark: str
    start: str
    end: str | None
    sector_label: str
    output_dir: Path
    assumptions_file: Path | None = None
    sec_user_agent: str = field(
        default_factory=lambda: os.getenv(
            "SEC_USER_AGENT",
            "Anklesh Research anklesh@example.com",
        )
    )
    fred_series: dict[str, str] = field(
        default_factory=lambda: {
            "US 10Y Treasury Yield": "DGS10",
            "Fed Funds Rate": "FEDFUNDS",
            "3M Treasury Bill": "DTB3",
            "US CPI Index": "CPIAUCSL",
            "US Unemployment Rate": "UNRATE",
            "High Yield Spread": "BAMLH0A0HYM2",
        }
    )
