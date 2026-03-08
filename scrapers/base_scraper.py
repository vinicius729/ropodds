"""Base scraper class for odds collection."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OddsData:
    """Standardized odds data from any site."""
    site_name: str
    site_type: str  # "main" or "competitor"
    championship: str = ""
    home_team: str = ""
    away_team: str = ""
    match_time: str = ""
    match_date: str = ""

    # 1X2
    odd_home: float | None = None
    odd_draw: float | None = None
    odd_away: float | None = None

    # BTTS
    odd_btts_yes: float | None = None
    odd_btts_no: float | None = None

    # Over/Under 2.5
    odd_over_25: float | None = None
    odd_under_25: float | None = None

    # Over/Under 1.5
    odd_over_15: float | None = None
    odd_under_15: float | None = None

    # Over/Under 3.5
    odd_over_35: float | None = None
    odd_under_35: float | None = None

    # Double Chance
    odd_dc_1x: float | None = None
    odd_dc_12: float | None = None
    odd_dc_x2: float | None = None

    def event_key(self) -> str:
        """Unique key for matching events across sites."""
        home = self.home_team.strip().lower()
        away = self.away_team.strip().lower()
        return f"{home}_vs_{away}_{self.match_date}"


class BaseScraper(ABC):
    """Abstract base scraper for odds sites."""

    def __init__(self, name: str, short_name: str, url: str, site_type: str = "competitor"):
        self.name = name
        self.short_name = short_name
        self.url = url
        self.site_type = site_type

    @abstractmethod
    async def scrape(self, target_date: str) -> list[OddsData]:
        """
        Scrape odds for a given date.

        Args:
            target_date: Date in YYYY-MM-DD format.

        Returns:
            List of OddsData for all events found.
        """
        pass

    def _parse_odd(self, value: str) -> float | None:
        """Parse an odds value string to float."""
        if not value or value.strip() in ("-", "N/A", "—", ""):
            return None
        try:
            cleaned = value.strip().replace(",", ".")
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _normalize_team_name(self, name: str) -> str:
        """Normalize team names for matching across sites."""
        if not name:
            return ""
        replacements = {
            "FC ": "", " FC": "", "CF ": "", " CF": "",
            "SC ": "", " SC": "", "EC ": "", " EC": "",
            "AC ": "", " AC": "", "SE ": "", " SE": "",
            "Atlético": "Atletico", "São": "Sao",
            "Grêmio": "Gremio", "Fluminense": "Fluminense",
            " de ": " ", " do ": " ", " da ": " ", " dos ": " ",
        }
        result = name.strip()
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result.strip()
