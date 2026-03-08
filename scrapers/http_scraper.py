"""HTTP-based scraper for white-label competitor betting sites.

These sites (ProSporte, MiamiBets, VegasPrime, TeamTop, etc.) use ASP.NET
server-rendered HTML. No JavaScript rendering needed — httpx + regex is
faster and more reliable than Playwright for real-time data collection.

Typical HTML structure:
    Date/Time
    [crest] Team A
    [crest] Team B
    [1.85] [2.70] [4.00]   ← odds in bracket notation with comma decimals
"""

import asyncio
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, OddsData

logger = logging.getLogger(__name__)

# Regex patterns for the white-label betting sites
ODDS_BRACKET = re.compile(r'\[(\d+[.,]\d{2})\]')
TIME_PATTERN = re.compile(r'(\d{1,2}/\w{3})?\s*(\d{1,2}:\d{2})')
TEAM_LINE = re.compile(r'^[A-ZÀ-Ú][\w\s\.\-/áéíóúãõâêîôûçÁÉÍÓÚÃÕÂÊÎÔÛÇ]+', re.UNICODE)


class HttpScraper(BaseScraper):
    """Fast HTTP scraper for white-label ASP.NET betting sites."""

    def __init__(self, name: str, short_name: str, url: str):
        super().__init__(name=name, short_name=short_name, url=url, site_type="competitor")

    async def scrape(self, target_date: str) -> list[OddsData]:
        if not self.url:
            logger.warning(f"[{self.short_name}] No URL configured, skipping")
            return []

        logger.info(f"[{self.short_name}] HTTP scraping {self.url}")
        results = []

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                verify=False,  # Some sites have SSL issues
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "pt-BR,pt;q=0.9",
                },
            ) as client:
                resp = await client.get(self.url)
                resp.raise_for_status()
                html = resp.text

                results = self._parse_html(html, target_date)
                logger.info(f"[{self.short_name}] Found {len(results)} events via HTTP")

        except httpx.TimeoutException:
            logger.error(f"[{self.short_name}] HTTP timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"[{self.short_name}] HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"[{self.short_name}] HTTP scraping error: {e}")

        # Fallback to Playwright if HTTP found nothing
        if not results:
            logger.info(f"[{self.short_name}] HTTP found nothing, trying Playwright fallback")
            results = await self._playwright_fallback(target_date)

        return results

    def _parse_html(self, html: str, target_date: str) -> list[OddsData]:
        """Parse HTML from white-label ASP.NET betting sites."""
        events = []

        # Strategy 1: Extract from text blocks with bracket-notation odds
        events = self._parse_text_blocks(html, target_date)

        # Strategy 2: Try BeautifulSoup structured parsing
        if not events:
            events = self._parse_with_soup(html, target_date)

        return events

    def _parse_text_blocks(self, html: str, target_date: str) -> list[OddsData]:
        """Parse odds from text content using bracket notation [X.XX]."""
        events = []

        # Get visible text from HTML
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        current_championship = ""
        i = 0

        while i < len(lines):
            line = lines[i]

            # Detect championship headers (typically short, capitalized, league-like)
            if self._looks_like_championship(line):
                current_championship = line
                i += 1
                continue

            # Look for odds in bracket format: [1.85] [2.70] [4.00]
            odds_matches = ODDS_BRACKET.findall(line)

            # Also try plain decimal odds on a line
            if not odds_matches:
                plain_odds = re.findall(r'\b(\d+[.,]\d{2})\b', line)
                if len(plain_odds) >= 3:
                    odds_matches = plain_odds

            if len(odds_matches) >= 3:
                # Found odds line — look back for team names
                home_team = ""
                away_team = ""
                match_time = ""

                for j in range(max(0, i - 5), i):
                    prev = lines[j]

                    # Skip lines that are odds or very short
                    if ODDS_BRACKET.search(prev) or len(prev) < 3:
                        continue

                    # Check for time/date pattern: "08/mar18:00", "18:00", etc.
                    time_match = TIME_PATTERN.search(prev)
                    if time_match:
                        match_time = time_match.group(2)
                        # If this line is ONLY a date/time, skip it
                        stripped = re.sub(r'\d{1,2}/\w{3}', '', prev).strip()
                        stripped = re.sub(r'\d{1,2}:\d{2}', '', stripped).strip()
                        if not stripped:
                            continue

                    # Check if it looks like a team name
                    if self._looks_like_team(prev):
                        if not home_team:
                            home_team = self._clean_team_name(prev)
                        elif not away_team:
                            away_team = self._clean_team_name(prev)

                if home_team and away_team:
                    events.append(OddsData(
                        site_name=self.short_name,
                        site_type=self.site_type,
                        championship=current_championship,
                        home_team=home_team,
                        away_team=away_team,
                        match_time=match_time,
                        match_date=target_date,
                        odd_home=self._parse_odd(odds_matches[0]),
                        odd_draw=self._parse_odd(odds_matches[1]),
                        odd_away=self._parse_odd(odds_matches[2]),
                    ))

            i += 1

        return events

    def _parse_with_soup(self, html: str, target_date: str) -> list[OddsData]:
        """Structured BeautifulSoup parsing as fallback."""
        events = []
        soup = BeautifulSoup(html, "html.parser")

        # Try common betting site table structures
        for selector in [
            "table tr",
            "[class*='event']",
            "[class*='match']",
            "[class*='game']",
            "div[class*='odd']",
        ]:
            elements = soup.select(selector)
            if len(elements) > 3:
                for el in elements:
                    text = el.get_text(separator="\n")
                    odds = ODDS_BRACKET.findall(text)
                    if not odds:
                        odds = re.findall(r'\b(\d+[.,]\d{2})\b', text)

                    if len(odds) >= 3:
                        # Extract team-like strings
                        text_lines = [
                            l.strip() for l in text.split("\n")
                            if l.strip() and not ODDS_BRACKET.search(l) and len(l.strip()) > 2
                        ]
                        teams = [l for l in text_lines if self._looks_like_team(l)]

                        if len(teams) >= 2:
                            events.append(OddsData(
                                site_name=self.short_name,
                                site_type=self.site_type,
                                home_team=self._clean_team_name(teams[0]),
                                away_team=self._clean_team_name(teams[1]),
                                match_date=target_date,
                                odd_home=self._parse_odd(odds[0]),
                                odd_draw=self._parse_odd(odds[1]),
                                odd_away=self._parse_odd(odds[2]),
                            ))

                if events:
                    break

        return events

    async def _playwright_fallback(self, target_date: str) -> list[OddsData]:
        """Fallback to Playwright for JavaScript-heavy sites."""
        try:
            from scrapers.generic_scraper import GenericScraper
            fallback = GenericScraper(
                name=self.name,
                short_name=self.short_name,
                url=self.url,
            )
            return await fallback.scrape(target_date)
        except Exception as e:
            logger.error(f"[{self.short_name}] Playwright fallback failed: {e}")
            return []

    def _looks_like_championship(self, text: str) -> bool:
        """Check if text looks like a championship/league name."""
        lower = text.lower()

        # "Brasil - Campeonato Carioca" format from white-label sites
        if re.match(r'^(brasil|itália|espanha|alemanha|frança|portugal|holanda|inglaterra|méxico|argentina|chile|uruguai|paraguai|equador|colômbia|peru|bélgica|turquia|grécia|croácia|escócia|dinamarca|noruega|polônia|hungria|rep\.|estados|costa|arábia|argélia|marrocos|jordânia|emirados|venezuela|guatemala|honduras|panamá|jamaica|nicarágua|romênia|sérvia|eslováquia|bósnia|albânia|ilhas)\s*-\s*.+', lower):
            return True

        keywords = [
            "serie a", "serie b", "serie c", "laliga", "bundesliga",
            "ligue 1", "premier", "eredivisie", "primeira liga",
            "campeonato", "copa", "league", "division", "liga",
            "paulista", "carioca", "gaúcho", "gaucho", "mineiro",
            "cearense", "baiano", "pernambucano", "paraense",
            "catarinense", "sergipano", "paraibano", "potiguar",
            "amapaense", "amazonense", "mato-grossense", "candango",
            "capixaba", "piauiense", "alagoano", "maranhense",
            "mls", "cup", "champions", "europa league",
            "jogos disponíveis", "rfef", "ekstraklasa", "superliga",
            "botola", "hnl", "pro league",
        ]
        return any(kw in lower for kw in keywords) and len(text) < 100

    def _looks_like_team(self, text: str) -> bool:
        """Check if text looks like a team name."""
        if not text or len(text) < 3 or len(text) > 60:
            return False
        if ODDS_BRACKET.search(text):
            return False
        if re.match(r'^[\d:./\-\s]+$', text):
            return False
        if text.startswith("[") or text.startswith("+"):
            return False

        lower = text.lower().strip()

        # Reject pure date/time strings: "08/mar", "08/mar18:00", "18:00"
        if re.match(r'^\d{1,2}/\w{3}(\d{2}:\d{2})?$', text.strip()):
            return False
        if re.match(r'^\d{1,2}:\d{2}$', text.strip()):
            return False

        # Reject known non-team patterns
        reject_patterns = [
            "domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado",
            "jogos disponíveis", "jogos disponivel", "casa", "empate", "fora",
            "futebol", "apostar", "apostas", "mercado", "mais opções",
            "simulador", "ticket", "validar", "login", "cadastro", "menu",
            "carrinho", "saldo", "conta", "buscar", "pesquisar", "filtro",
            "ao vivo", "resultado", "estatística", "regras", "termos",
            "contato", "suporte", "ajuda", "promoção", "bônus",
            "brasil -", "itália -", "espanha -", "alemanha -", "frança -",
            "portugal -", "holanda -", "inglaterra -", "méxico -",
        ]
        if any(p in lower for p in reject_patterns):
            return False

        # Reject if it's a championship header
        if self._looks_like_championship(text):
            return False

        # Should have at least some letters
        return bool(re.search(r'[A-Za-zÀ-ÿ]{2,}', text))

    def _clean_team_name(self, name: str) -> str:
        """Clean up a team name."""
        # Remove common prefixes/suffixes
        name = re.sub(r'^\d+\.\s*', '', name)  # "1. Team Name"
        name = re.sub(r'\s*\(.*?\)\s*$', '', name)  # "Team (Country)"
        return name.strip()

    def _parse_odd(self, value: str) -> float | None:
        """Parse odds value, handling comma decimal format."""
        if not value:
            return None
        try:
            cleaned = value.strip().replace(",", ".")
            val = float(cleaned)
            return val if 1.0 <= val <= 100.0 else None
        except (ValueError, TypeError):
            return None
