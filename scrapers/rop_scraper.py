"""Scraper for the ROP/DP Sports site (ropsolucoes.com)."""

import asyncio
import logging
import re

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from scrapers.base_scraper import BaseScraper, OddsData

logger = logging.getLogger(__name__)


class ROPScraper(BaseScraper):
    """Scraper for ropsolucoes.com — the main DP Sports site."""

    def __init__(self):
        super().__init__(
            name="ROP/DP Sports",
            short_name="ROP",
            url="https://www.ropsolucoes.com",
            site_type="main",
        )

    async def scrape(self, target_date: str) -> list[OddsData]:
        """
        Navigate to ROP site for the given date and extract all football odds.

        The site is a Next.js app, so we need a real browser to render JavaScript.
        """
        url = f"{self.url}/?startTimeUtc={target_date}"
        logger.info(f"[ROP] Scraping {url}")

        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="pt-BR",
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                # Wait for content to load
                await page.wait_for_timeout(5000)

                results = await self._extract_events(page, target_date)
                logger.info(f"[ROP] Found {len(results)} events")

            except PlaywrightTimeout:
                logger.error("[ROP] Page load timeout")
            except Exception as e:
                logger.error(f"[ROP] Scraping error: {e}")
            finally:
                await browser.close()

        return results

    async def _extract_events(self, page: Page, target_date: str) -> list[OddsData]:
        """Extract events and odds from the loaded page."""
        events = []

        # Strategy 1: Try to find structured event elements
        # Common patterns in betting sites built with Next.js
        selectors_to_try = [
            # Try common betting site patterns
            "[class*='event']",
            "[class*='match']",
            "[class*='game']",
            "[class*='fixture']",
            "[data-event]",
            "[data-match]",
            "tr[class*='odd']",
            ".market-row",
            # Generic table rows with odds
            "table tbody tr",
        ]

        for selector in selectors_to_try:
            elements = await page.query_selector_all(selector)
            if elements and len(elements) > 2:
                logger.info(f"[ROP] Found {len(elements)} elements with selector: {selector}")
                events = await self._parse_event_elements(page, elements, target_date, selector)
                if events:
                    break

        # Strategy 2: If no structured elements found, try extracting from page text
        if not events:
            logger.info("[ROP] Falling back to text-based extraction")
            events = await self._extract_from_text(page, target_date)

        # Strategy 3: Intercept network requests for API data
        if not events:
            logger.info("[ROP] Trying API interception approach")
            events = await self._extract_from_api(page, target_date)

        return events

    async def _parse_event_elements(
        self, page: Page, elements: list, target_date: str, selector: str
    ) -> list[OddsData]:
        """Parse structured event elements into OddsData."""
        events = []

        for element in elements:
            try:
                text = await element.inner_text()
                if not text.strip():
                    continue

                # Try to extract team names and odds from the element
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                # Look for odds patterns (numbers like 1.50, 2.30, etc.)
                odds_pattern = re.compile(r'\b\d+\.\d{2}\b')
                odds_values = odds_pattern.findall(text)

                if len(odds_values) >= 3:
                    # Try to identify team names (non-numeric, non-short text)
                    team_candidates = [
                        l for l in lines
                        if not odds_pattern.match(l) and len(l) > 2 and not l.replace(":", "").isdigit()
                    ]

                    if len(team_candidates) >= 2:
                        odds = OddsData(
                            site_name=self.short_name,
                            site_type=self.site_type,
                            home_team=team_candidates[0],
                            away_team=team_candidates[1],
                            match_date=target_date,
                            odd_home=self._parse_odd(odds_values[0]),
                            odd_draw=self._parse_odd(odds_values[1]) if len(odds_values) > 1 else None,
                            odd_away=self._parse_odd(odds_values[2]) if len(odds_values) > 2 else None,
                        )

                        # Try to get championship from parent/sibling
                        try:
                            parent = await element.evaluate_handle("el => el.closest('[class*=\"league\"], [class*=\"champ\"], [class*=\"tournament\"], [class*=\"competition\"]')")
                            if parent:
                                champ_text = await parent.inner_text()
                                if champ_text:
                                    odds.championship = champ_text.split("\n")[0].strip()
                        except Exception:
                            pass

                        # Try to get match time
                        time_pattern = re.compile(r'\b\d{1,2}:\d{2}\b')
                        time_matches = time_pattern.findall(text)
                        if time_matches:
                            odds.match_time = time_matches[0]

                        events.append(odds)

            except Exception as e:
                logger.debug(f"[ROP] Error parsing element: {e}")
                continue

        return events

    async def _extract_from_text(self, page: Page, target_date: str) -> list[OddsData]:
        """Fallback: extract events from full page text content."""
        events = []
        try:
            content = await page.content()

            # Look for JSON data in script tags
            json_pattern = re.compile(r'<script[^>]*>.*?(\{.*?"odds".*?\}).*?</script>', re.DOTALL)
            matches = json_pattern.findall(content)

            # Also look for __NEXT_DATA__
            next_data = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
            nd_match = next_data.search(content)
            if nd_match:
                import json
                try:
                    data = json.loads(nd_match.group(1))
                    events = self._parse_next_data(data, target_date)
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.error(f"[ROP] Text extraction error: {e}")

        return events

    async def _extract_from_api(self, page: Page, target_date: str) -> list[OddsData]:
        """Try to intercept API calls by reloading the page with network monitoring."""
        events = []
        api_responses = []

        async def handle_response(response):
            url = response.url
            if any(kw in url.lower() for kw in ["event", "odds", "match", "fixture", "sport", "api"]):
                try:
                    if "json" in (response.headers.get("content-type", "")):
                        body = await response.json()
                        api_responses.append({"url": url, "data": body})
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            await page.reload(wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)
        except Exception:
            pass

        for resp in api_responses:
            logger.info(f"[ROP] Captured API: {resp['url']}")
            parsed = self._parse_api_response(resp["data"], target_date)
            events.extend(parsed)

        return events

    def _parse_next_data(self, data: dict, target_date: str) -> list[OddsData]:
        """Parse __NEXT_DATA__ JSON for events."""
        events = []
        # Walk the data structure looking for event-like objects
        self._walk_dict(data, events, target_date)
        return events

    def _walk_dict(self, obj, events: list, target_date: str, depth: int = 0):
        """Recursively walk a dict looking for event data."""
        if depth > 15:
            return

        if isinstance(obj, dict):
            # Check if this looks like an event object
            has_teams = any(k in obj for k in ["home", "away", "homeTeam", "awayTeam", "home_team", "away_team"])
            has_odds = any(k in obj for k in ["odds", "markets", "prices", "selections"])

            if has_teams and has_odds:
                event = self._dict_to_odds(obj, target_date)
                if event:
                    events.append(event)

            for v in obj.values():
                self._walk_dict(v, events, target_date, depth + 1)

        elif isinstance(obj, list):
            for item in obj:
                self._walk_dict(item, events, target_date, depth + 1)

    def _dict_to_odds(self, obj: dict, target_date: str) -> OddsData | None:
        """Convert a detected event dict to OddsData."""
        try:
            home = obj.get("home") or obj.get("homeTeam") or obj.get("home_team", "")
            away = obj.get("away") or obj.get("awayTeam") or obj.get("away_team", "")

            if isinstance(home, dict):
                home = home.get("name", "")
            if isinstance(away, dict):
                away = away.get("name", "")

            if not home or not away:
                return None

            odds = obj.get("odds") or obj.get("markets") or obj.get("prices", {})
            odd_home = odd_draw = odd_away = None

            if isinstance(odds, dict):
                odd_home = self._parse_odd(str(odds.get("1") or odds.get("home", "")))
                odd_draw = self._parse_odd(str(odds.get("X") or odds.get("draw", "")))
                odd_away = self._parse_odd(str(odds.get("2") or odds.get("away", "")))
            elif isinstance(odds, list) and len(odds) >= 3:
                odd_home = self._parse_odd(str(odds[0]))
                odd_draw = self._parse_odd(str(odds[1]))
                odd_away = self._parse_odd(str(odds[2]))

            return OddsData(
                site_name=self.short_name,
                site_type=self.site_type,
                championship=obj.get("league", obj.get("championship", obj.get("competition", ""))),
                home_team=str(home),
                away_team=str(away),
                match_time=obj.get("time", obj.get("kickoff", "")),
                match_date=target_date,
                odd_home=odd_home,
                odd_draw=odd_draw,
                odd_away=odd_away,
            )
        except Exception as e:
            logger.debug(f"[ROP] Error converting dict to odds: {e}")
            return None

    def _parse_api_response(self, data, target_date: str) -> list[OddsData]:
        """Parse an intercepted API response."""
        events = []
        self._walk_dict(data, events, target_date)
        return events
