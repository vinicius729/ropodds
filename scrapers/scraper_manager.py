"""Scraper Manager — orchestrates scraping across all sites."""

import asyncio
import logging
from datetime import datetime

import yaml

from scrapers.base_scraper import OddsData
from scrapers.rop_scraper import ROPScraper
from scrapers.generic_scraper import GenericScraper

logger = logging.getLogger(__name__)


class ScraperManager:
    """Manages and runs all site scrapers."""

    def __init__(self, sites_config_path: str = "config/sites.yaml"):
        self.scrapers: list = []
        self._load_config(sites_config_path)

    def _load_config(self, config_path: str):
        """Load site configurations and instantiate scrapers."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}. Using defaults.")
            config = {}

        # Main site — always use the specialized ROP scraper
        self.scrapers.append(ROPScraper())

        # Competitors
        competitors = config.get("competitors", [])
        for comp in competitors:
            url = comp.get("url", "")
            if url:  # Only add scrapers with configured URLs
                self.scrapers.append(GenericScraper(
                    name=comp["name"],
                    short_name=comp["short_name"],
                    url=url,
                    selectors=comp.get("selectors"),
                ))
            else:
                logger.info(f"Skipping {comp['name']} — no URL configured")

    async def scrape_all(self, target_date: str | None = None) -> dict[str, list[OddsData]]:
        """
        Scrape all configured sites concurrently.

        Args:
            target_date: Date in YYYY-MM-DD format. Defaults to today.

        Returns:
            Dict mapping site short names to their scraped OddsData lists.
        """
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"Starting scrape for date: {target_date}")
        logger.info(f"Active scrapers: {[s.short_name for s in self.scrapers]}")

        # Run all scrapers concurrently
        tasks = [scraper.scrape(target_date) for scraper in self.scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_data: dict[str, list[OddsData]] = {}
        for scraper, result in zip(self.scrapers, results):
            if isinstance(result, Exception):
                logger.error(f"[{scraper.short_name}] Scraper failed: {result}")
                all_data[scraper.short_name] = []
            else:
                all_data[scraper.short_name] = result

        total = sum(len(v) for v in all_data.values())
        logger.info(f"Scraping complete. Total records: {total}")
        return all_data

    async def scrape_main_site(self, target_date: str | None = None) -> list[OddsData]:
        """Scrape only the main ROP site."""
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d")

        rop = self.scrapers[0]  # ROP is always first
        return await rop.scrape(target_date)
