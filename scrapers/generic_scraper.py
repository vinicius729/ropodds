"""Generic Playwright-based scraper for competitor betting sites."""

import asyncio
import logging
import re

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from scrapers.base_scraper import BaseScraper, OddsData

logger = logging.getLogger(__name__)


class GenericScraper(BaseScraper):
    """
    Generic scraper that works with most betting sites.

    Uses multiple strategies:
    1. CSS selector-based extraction (configurable per site)
    2. Pattern matching on page content
    3. API interception
    """

    def __init__(self, name: str, short_name: str, url: str, selectors: dict | None = None):
        super().__init__(name=name, short_name=short_name, url=url, site_type="competitor")
        self.selectors = selectors or {}

    async def scrape(self, target_date: str) -> list[OddsData]:
        """Scrape odds from the competitor site."""
        if not self.url:
            logger.warning(f"[{self.short_name}] No URL configured, skipping")
            return []

        logger.info(f"[{self.short_name}] Scraping {self.url}")
        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="pt-BR",
            )
            page = await context.new_page()

            # Capture API responses
            api_responses = []

            async def capture_response(response):
                url = response.url
                ct = response.headers.get("content-type", "")
                if "json" in ct and any(
                    kw in url.lower()
                    for kw in ["event", "odds", "match", "fixture", "sport", "api", "market"]
                ):
                    try:
                        body = await response.json()
                        api_responses.append({"url": url, "data": body})
                    except Exception:
                        pass

            page.on("response", capture_response)

            try:
                await page.goto(self.url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)

                # Strategy 1: Use configured selectors
                if self.selectors.get("event_container"):
                    results = await self._extract_with_selectors(page, target_date)

                # Strategy 2: Pattern-based extraction
                if not results:
                    results = await self._extract_with_patterns(page, target_date)

                # Strategy 3: Use captured API data
                if not results and api_responses:
                    for resp in api_responses:
                        parsed = self._parse_api_data(resp["data"], target_date)
                        results.extend(parsed)

                logger.info(f"[{self.short_name}] Found {len(results)} events")

            except PlaywrightTimeout:
                logger.error(f"[{self.short_name}] Page load timeout")
            except Exception as e:
                logger.error(f"[{self.short_name}] Scraping error: {e}")
            finally:
                await browser.close()

        return results

    async def _extract_with_selectors(self, page: Page, target_date: str) -> list[OddsData]:
        """Extract using configured CSS selectors."""
        events = []
        container_sel = self.selectors.get("event_container", "")
        if not container_sel:
            return events

        containers = await page.query_selector_all(container_sel)
        for container in containers:
            try:
                home = ""
                away = ""
                odds_vals = []

                if self.selectors.get("home_team"):
                    el = await container.query_selector(self.selectors["home_team"])
                    if el:
                        home = (await el.inner_text()).strip()

                if self.selectors.get("away_team"):
                    el = await container.query_selector(self.selectors["away_team"])
                    if el:
                        away = (await el.inner_text()).strip()

                if self.selectors.get("odds_1x2"):
                    els = await container.query_selector_all(self.selectors["odds_1x2"])
                    for el in els:
                        txt = (await el.inner_text()).strip()
                        odds_vals.append(txt)

                if home and away and len(odds_vals) >= 3:
                    events.append(OddsData(
                        site_name=self.short_name,
                        site_type=self.site_type,
                        home_team=home,
                        away_team=away,
                        match_date=target_date,
                        odd_home=self._parse_odd(odds_vals[0]),
                        odd_draw=self._parse_odd(odds_vals[1]),
                        odd_away=self._parse_odd(odds_vals[2]),
                    ))
            except Exception as e:
                logger.debug(f"[{self.short_name}] Selector parse error: {e}")

        return events

    async def _extract_with_patterns(self, page: Page, target_date: str) -> list[OddsData]:
        """Extract using text pattern matching."""
        events = []
        try:
            # Get all visible text blocks that look like event rows
            all_text = await page.inner_text("body")

            # Pattern: team names followed by odds
            # Common: "Team A    Team B    1.50  3.20  4.50"
            lines = all_text.split("\n")
            odds_pattern = re.compile(r'\b(\d+\.\d{2})\b')

            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue

                odds_in_line = odds_pattern.findall(line)
                if len(odds_in_line) >= 3:
                    # This line has odds, try to find team names nearby
                    # Look at preceding lines for team names
                    home = ""
                    away = ""

                    for j in range(max(0, i - 3), i):
                        prev = lines[j].strip()
                        if prev and not odds_pattern.search(prev) and len(prev) > 2:
                            if not home:
                                home = prev
                            elif not away:
                                away = prev

                    # Or team names might be in the same line before the odds
                    if not home:
                        text_before_odds = odds_pattern.split(line)[0].strip()
                        parts = re.split(r'\s{2,}|\t|vs\.?|x\s', text_before_odds, flags=re.IGNORECASE)
                        parts = [p.strip() for p in parts if p.strip()]
                        if len(parts) >= 2:
                            home = parts[0]
                            away = parts[1]

                    if home and away:
                        events.append(OddsData(
                            site_name=self.short_name,
                            site_type=self.site_type,
                            home_team=home,
                            away_team=away,
                            match_date=target_date,
                            odd_home=self._parse_odd(odds_in_line[0]),
                            odd_draw=self._parse_odd(odds_in_line[1]),
                            odd_away=self._parse_odd(odds_in_line[2]),
                        ))

                i += 1

        except Exception as e:
            logger.error(f"[{self.short_name}] Pattern extraction error: {e}")

        return events

    def _parse_api_data(self, data, target_date: str) -> list[OddsData]:
        """Parse intercepted API JSON data."""
        events = []
        self._walk_for_events(data, events, target_date, depth=0)
        return events

    def _walk_for_events(self, obj, events: list, target_date: str, depth: int):
        """Recursively walk JSON looking for event/odds structures."""
        if depth > 15:
            return

        if isinstance(obj, dict):
            has_teams = any(
                k in obj
                for k in [
                    "home", "away", "homeTeam", "awayTeam",
                    "home_team", "away_team", "team1", "team2",
                    "competitors", "participants",
                ]
            )
            has_odds = any(
                k in obj
                for k in ["odds", "markets", "prices", "selections", "outcomes"]
            )

            if has_teams:
                event = self._api_dict_to_odds(obj, target_date)
                if event:
                    events.append(event)
            else:
                for v in obj.values():
                    self._walk_for_events(v, events, target_date, depth + 1)

        elif isinstance(obj, list):
            for item in obj:
                self._walk_for_events(item, events, target_date, depth + 1)

    def _api_dict_to_odds(self, obj: dict, target_date: str) -> OddsData | None:
        """Convert an API event dict to OddsData."""
        try:
            # Extract team names
            home = (
                obj.get("home")
                or obj.get("homeTeam")
                or obj.get("home_team")
                or obj.get("team1", "")
            )
            away = (
                obj.get("away")
                or obj.get("awayTeam")
                or obj.get("away_team")
                or obj.get("team2", "")
            )

            # Handle nested team objects
            if isinstance(home, dict):
                home = home.get("name", home.get("teamName", ""))
            if isinstance(away, dict):
                away = away.get("name", away.get("teamName", ""))

            # Handle competitors/participants array
            if not home and "competitors" in obj:
                comps = obj["competitors"]
                if isinstance(comps, list) and len(comps) >= 2:
                    home = comps[0] if isinstance(comps[0], str) else comps[0].get("name", "")
                    away = comps[1] if isinstance(comps[1], str) else comps[1].get("name", "")

            if not home or not away:
                return None

            # Extract odds
            odd_home = odd_draw = odd_away = None
            odds_data = obj.get("odds") or obj.get("markets") or obj.get("prices", {})

            if isinstance(odds_data, dict):
                # Try common key patterns
                for h_key in ["1", "home", "h", "1x2_home"]:
                    if h_key in odds_data:
                        odd_home = self._parse_odd(str(odds_data[h_key]))
                        break
                for d_key in ["X", "x", "draw", "d", "1x2_draw"]:
                    if d_key in odds_data:
                        odd_draw = self._parse_odd(str(odds_data[d_key]))
                        break
                for a_key in ["2", "away", "a", "1x2_away"]:
                    if a_key in odds_data:
                        odd_away = self._parse_odd(str(odds_data[a_key]))
                        break
            elif isinstance(odds_data, list) and len(odds_data) >= 3:
                odd_home = self._parse_odd(str(odds_data[0]))
                odd_draw = self._parse_odd(str(odds_data[1]))
                odd_away = self._parse_odd(str(odds_data[2]))

            champ = (
                obj.get("league")
                or obj.get("championship")
                or obj.get("competition")
                or obj.get("tournament", "")
            )
            if isinstance(champ, dict):
                champ = champ.get("name", "")

            return OddsData(
                site_name=self.short_name,
                site_type=self.site_type,
                championship=str(champ),
                home_team=str(home),
                away_team=str(away),
                match_time=str(obj.get("time") or obj.get("startTime") or obj.get("kickoff", "")),
                match_date=target_date,
                odd_home=odd_home,
                odd_draw=odd_draw,
                odd_away=odd_away,
            )
        except Exception:
            return None
