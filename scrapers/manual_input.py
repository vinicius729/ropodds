"""Manual data input parser — for pasting odds data in text format."""

import re
import logging
from scrapers.base_scraper import OddsData

logger = logging.getLogger(__name__)


def parse_manual_input(text: str, target_date: str = "") -> list[OddsData]:
    """
    Parse manually collected odds data in the template format.

    Expected format:
        Jogo: Time Casa vs Time Fora
        Campeonato: Nome do Campeonato
        Horário: HH:MM BRT

        # Odds 1X2 (Casa, Empate, Fora)
        ROP: 1.50, 3.20, 4.50
        ProSporte: 1.55, 3.10, 4.40
        ...

        # Ambos Marcam (Sim, Não)
        ROP: 1.80, 1.90

        # Mais/Menos 2.5 Gols (Mais, Menos)
        ROP: 1.70, 2.10
    """
    events = []
    blocks = re.split(r'(?=Jogo:)', text, flags=re.IGNORECASE)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        parsed = _parse_event_block(block, target_date)
        events.extend(parsed)

    logger.info(f"[Manual] Parsed {len(events)} odds records from input")
    return events


def _parse_event_block(block: str, target_date: str) -> list[OddsData]:
    """Parse a single event block into multiple OddsData (one per site)."""
    records = []

    # Extract event info
    jogo_match = re.search(r'Jogo:\s*(.+?)\s*vs\.?\s*(.+)', block, re.IGNORECASE)
    if not jogo_match:
        return records

    home_team = jogo_match.group(1).strip()
    away_team = jogo_match.group(2).strip()

    champ_match = re.search(r'Campeonato:\s*(.+)', block, re.IGNORECASE)
    championship = champ_match.group(1).strip() if champ_match else ""

    time_match = re.search(r'Hor[áa]rio:\s*(\d{1,2}:\d{2})', block, re.IGNORECASE)
    match_time = time_match.group(1) if time_match else ""

    # Extract 1X2 odds section
    x12_section = re.search(
        r'#\s*Odds\s*1X2.*?\n(.*?)(?=#|\Z)',
        block, re.IGNORECASE | re.DOTALL
    )

    site_odds = {}  # site_name -> OddsData

    if x12_section:
        for line in x12_section.group(1).strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r'(.+?):\s*([\d.,\-\s]+)', line)
            if not match:
                continue

            site_name = match.group(1).strip()
            values = [v.strip() for v in match.group(2).split(",")]

            site_type = "main" if site_name.upper() in ("ROP", "ROP/DP SPORTS", "DPSPORTS") else "competitor"
            short_name = "ROP" if site_type == "main" else site_name

            odds = OddsData(
                site_name=short_name,
                site_type=site_type,
                championship=championship,
                home_team=home_team,
                away_team=away_team,
                match_time=match_time,
                match_date=target_date,
            )

            if len(values) >= 1:
                odds.odd_home = _parse_val(values[0])
            if len(values) >= 2:
                odds.odd_draw = _parse_val(values[1])
            if len(values) >= 3:
                odds.odd_away = _parse_val(values[2])

            site_odds[short_name] = odds

    # Extract BTTS section (only ROP typically)
    btts_section = re.search(
        r'#\s*Ambos\s*Marcam.*?\n(.*?)(?=#|\Z)',
        block, re.IGNORECASE | re.DOTALL
    )
    if btts_section:
        for line in btts_section.group(1).strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r'(.+?):\s*([\d.,\-\s]+)', line)
            if match:
                site_name = match.group(1).strip()
                short_name = "ROP" if site_name.upper() in ("ROP", "ROP/DP SPORTS") else site_name
                values = [v.strip() for v in match.group(2).split(",")]

                if short_name in site_odds:
                    if len(values) >= 1:
                        site_odds[short_name].odd_btts_yes = _parse_val(values[0])
                    if len(values) >= 2:
                        site_odds[short_name].odd_btts_no = _parse_val(values[1])

    # Extract Over/Under 2.5 section
    ou_section = re.search(
        r'#\s*Mais/Menos\s*2\.?5.*?\n(.*?)(?=#|\Z)',
        block, re.IGNORECASE | re.DOTALL
    )
    if ou_section:
        for line in ou_section.group(1).strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r'(.+?):\s*([\d.,\-\s]+)', line)
            if match:
                site_name = match.group(1).strip()
                short_name = "ROP" if site_name.upper() in ("ROP", "ROP/DP SPORTS") else site_name
                values = [v.strip() for v in match.group(2).split(",")]

                if short_name in site_odds:
                    if len(values) >= 1:
                        site_odds[short_name].odd_over_25 = _parse_val(values[0])
                    if len(values) >= 2:
                        site_odds[short_name].odd_under_25 = _parse_val(values[1])

    records = list(site_odds.values())
    return records


def _parse_val(value: str) -> float | None:
    """Parse a single odds value."""
    if not value or value.strip() in ("-", "N/A", "—", ""):
        return None
    try:
        return float(value.strip().replace(",", "."))
    except (ValueError, TypeError):
        return None
