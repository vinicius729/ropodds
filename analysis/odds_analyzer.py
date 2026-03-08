"""Odds Analysis Engine — compares ROP odds against competitor averages."""

import logging
from dataclasses import dataclass, field
from statistics import mean

from scrapers.base_scraper import OddsData
from config.settings import ALERT_THRESHOLD_ABOVE, ALERT_THRESHOLD_BELOW

logger = logging.getLogger(__name__)


@dataclass
class MarketAnalysis:
    """Analysis of a single market (e.g., 1X2 Home) for one event."""
    market_name: str        # e.g., "1X2 - Casa", "BTTS - Sim"
    rop_odd: float | None
    competitor_odds: dict[str, float]  # site_name -> odd
    avg_competitors: float | None = None
    best_odd: float | None = None
    best_odd_site: str = ""
    deviation_pct: float = 0.0
    status: str = "neutral"  # "above", "below", "neutral"
    status_emoji: str = "➡️"

    def calculate(self):
        """Calculate averages, deviations, and status."""
        valid_odds = [v for v in self.competitor_odds.values() if v is not None and v > 0]

        if valid_odds:
            self.avg_competitors = round(mean(valid_odds), 2)

            # Best odd across all competitors
            self.best_odd = max(valid_odds)
            for site, odd in self.competitor_odds.items():
                if odd == self.best_odd:
                    self.best_odd_site = site
                    break

        # Check if ROP beats best
        if self.rop_odd and self.best_odd and self.rop_odd >= self.best_odd:
            self.best_odd = self.rop_odd
            self.best_odd_site = "ROP"

        # Calculate deviation
        if self.rop_odd and self.avg_competitors and self.avg_competitors > 0:
            self.deviation_pct = round(
                ((self.rop_odd - self.avg_competitors) / self.avg_competitors) * 100, 1
            )

            if self.deviation_pct > ALERT_THRESHOLD_ABOVE:
                self.status = "above"
                self.status_emoji = "✅"
            elif self.deviation_pct < -ALERT_THRESHOLD_BELOW:
                self.status = "below"
                self.status_emoji = "⚠️"
            else:
                self.status = "neutral"
                self.status_emoji = "➡️"


@dataclass
class EventAnalysis:
    """Complete analysis of one event across all markets."""
    championship: str
    home_team: str
    away_team: str
    match_time: str
    match_date: str
    markets: dict[str, MarketAnalysis] = field(default_factory=dict)
    overall_status: str = "neutral"
    overall_emoji: str = "➡️"

    def determine_overall_status(self):
        """Determine overall event status based on 1X2 market."""
        statuses = [m.status for m in self.markets.values() if m.rop_odd is not None]
        if "above" in statuses and "below" not in statuses:
            self.overall_status = "above"
            self.overall_emoji = "✅"
        elif "below" in statuses and "above" not in statuses:
            self.overall_status = "below"
            self.overall_emoji = "⚠️"
        elif "above" in statuses and "below" in statuses:
            self.overall_status = "mixed"
            self.overall_emoji = "⚠️/✅"
        else:
            self.overall_status = "neutral"
            self.overall_emoji = "➡️"

    @property
    def has_alerts(self) -> bool:
        return any(m.status in ("above", "below") for m in self.markets.values())


@dataclass
class AlertItem:
    """A single alert for Telegram notification."""
    championship: str
    home_team: str
    away_team: str
    match_time: str
    market: str
    rop_odd: float
    market_avg: float
    deviation_pct: float
    alert_type: str  # "above" or "below"
    best_odd: float | None = None
    best_odd_site: str = ""


class OddsAnalyzer:
    """Analyzes odds data and produces structured analysis results."""

    def __init__(self):
        self.events: list[EventAnalysis] = []
        self.alerts: list[AlertItem] = []

    def analyze(self, all_data: dict[str, list[OddsData]]) -> list[EventAnalysis]:
        """
        Analyze all scraped data.

        Args:
            all_data: Dict of site_name -> list of OddsData

        Returns:
            List of EventAnalysis objects.
        """
        self.events = []
        self.alerts = []

        # Group data by event (home_team + away_team + date)
        event_map: dict[str, dict[str, OddsData]] = {}

        for site_name, odds_list in all_data.items():
            for odds in odds_list:
                key = odds.event_key()
                if key not in event_map:
                    event_map[key] = {}
                event_map[key][odds.site_name] = odds

        # Analyze each event
        for event_key, site_data in event_map.items():
            # Get ROP data
            rop_data = site_data.get("ROP")
            competitor_data = {k: v for k, v in site_data.items() if k != "ROP"}

            # Use any available data for event metadata
            ref = rop_data or next(iter(site_data.values()))

            event = EventAnalysis(
                championship=ref.championship,
                home_team=ref.home_team,
                away_team=ref.away_team,
                match_time=ref.match_time,
                match_date=ref.match_date,
            )

            # Analyze 1X2 markets
            for market_key, market_name, attr in [
                ("1x2_home", "1X2 - Casa", "odd_home"),
                ("1x2_draw", "1X2 - Empate", "odd_draw"),
                ("1x2_away", "1X2 - Fora", "odd_away"),
            ]:
                rop_val = getattr(rop_data, attr, None) if rop_data else None
                comp_odds = {}
                for site, data in competitor_data.items():
                    val = getattr(data, attr, None)
                    if val is not None:
                        comp_odds[site] = val

                market = MarketAnalysis(
                    market_name=market_name,
                    rop_odd=rop_val,
                    competitor_odds=comp_odds,
                )
                market.calculate()
                event.markets[market_key] = market

                # Generate alert if needed
                if market.status in ("above", "below") and rop_val:
                    self.alerts.append(AlertItem(
                        championship=event.championship,
                        home_team=event.home_team,
                        away_team=event.away_team,
                        match_time=event.match_time,
                        market=market_name,
                        rop_odd=rop_val,
                        market_avg=market.avg_competitors or 0,
                        deviation_pct=market.deviation_pct,
                        alert_type=market.status,
                        best_odd=market.best_odd,
                        best_odd_site=market.best_odd_site,
                    ))

            # Analyze secondary markets (BTTS, O/U 2.5)
            for market_key, market_name, attr in [
                ("btts_yes", "Ambos Marcam - Sim", "odd_btts_yes"),
                ("btts_no", "Ambos Marcam - Não", "odd_btts_no"),
                ("over_25", "Mais 2.5 Gols", "odd_over_25"),
                ("under_25", "Menos 2.5 Gols", "odd_under_25"),
            ]:
                rop_val = getattr(rop_data, attr, None) if rop_data else None
                comp_odds = {}
                for site, data in competitor_data.items():
                    val = getattr(data, attr, None)
                    if val is not None:
                        comp_odds[site] = val

                if rop_val is not None or comp_odds:
                    market = MarketAnalysis(
                        market_name=market_name,
                        rop_odd=rop_val,
                        competitor_odds=comp_odds,
                    )
                    market.calculate()
                    event.markets[market_key] = market

            event.determine_overall_status()
            self.events.append(event)

        # Sort: events with alerts first, then by championship
        self.events.sort(key=lambda e: (
            0 if e.has_alerts else 1,
            e.championship or "ZZZ",
            e.match_time or "99:99",
        ))

        logger.info(f"Analysis complete: {len(self.events)} events, {len(self.alerts)} alerts")
        return self.events

    def get_opportunities(self) -> list[AlertItem]:
        """Get alerts where ROP is above average."""
        return [a for a in self.alerts if a.alert_type == "above"]

    def get_attention_points(self) -> list[AlertItem]:
        """Get alerts where ROP is below average."""
        return [a for a in self.alerts if a.alert_type == "below"]

    def get_summary_stats(self) -> dict:
        """Get summary statistics."""
        total_events = len(self.events)
        rop_covered = sum(
            1 for e in self.events
            if any(m.rop_odd is not None for m in e.markets.values())
        )

        championships_covered = set()
        championships_missing = set()
        for e in self.events:
            has_rop = any(m.rop_odd is not None for m in e.markets.values())
            if has_rop:
                championships_covered.add(e.championship)
            else:
                championships_missing.add(e.championship)

        # Remove covered from missing
        championships_missing -= championships_covered

        return {
            "total_events": total_events,
            "rop_covered": rop_covered,
            "alerts_above": len(self.get_opportunities()),
            "alerts_below": len(self.get_attention_points()),
            "championships_covered": sorted(championships_covered),
            "championships_missing": sorted(championships_missing),
        }
