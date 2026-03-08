import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Schedule
SCHEDULE_TIMES = os.getenv("SCHEDULE_TIMES", "09:00,14:00,17:00,19:00").split(",")
TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")

# Dashboard — PORT env is set by Railway/Render/Fly.io automatically
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("PORT", os.getenv("DASHBOARD_PORT", "5000")))
DASHBOARD_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "rop-odds-secret-key")

# API Key for webhook authentication
API_KEY = os.getenv("API_KEY", "rop-default-api-key")

# Alert Thresholds (percentage)
ALERT_THRESHOLD_ABOVE = float(os.getenv("ALERT_THRESHOLD_ABOVE", "3.0"))
ALERT_THRESHOLD_BELOW = float(os.getenv("ALERT_THRESHOLD_BELOW", "3.0"))

# Scraping
HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "true").lower() == "true"
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "30000"))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/ropodds.db")

# Sites Configuration
MAIN_SITE = {
    "name": "ROP/DP Sports",
    "short_name": "ROP",
    "url": "https://www.ropsolucoes.com",
    "type": "main",
}

COMPETITOR_SITES = [
    {"name": "ProSporte", "short_name": "ProSporte", "url": "", "type": "competitor"},
    {"name": "TeamBets", "short_name": "TeamBets", "url": "", "type": "competitor"},
    {"name": "VegasPrime", "short_name": "VegasPrime", "url": "", "type": "competitor"},
    {"name": "MiamiBets", "short_name": "MiamiBets", "url": "", "type": "competitor"},
    {"name": "TeamTop", "short_name": "TeamTop", "url": "", "type": "competitor"},
    {"name": "TMJBet", "short_name": "TMJBet", "url": "", "type": "competitor"},
    {"name": "MundoBets", "short_name": "MundoBets", "url": "", "type": "competitor"},
    {"name": "SportBetBrasil", "short_name": "SportBetBrasil", "url": "", "type": "competitor"},
    {"name": "Fanáticos Sportes", "short_name": "Fanáticos", "url": "", "type": "competitor"},
]

ALL_SITES = [MAIN_SITE] + COMPETITOR_SITES

# Championships
TIER1_CHAMPIONSHIPS = [
    "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "Premier League",
    "FA Cup", "Champions League", "Europa League", "Eredivisie",
]

BRAZIL_CHAMPIONSHIPS = [
    "Brasileirão Série A", "Brasileirão Série B",
    "Campeonato Baiano", "Campeonato Carioca", "Campeonato Catarinense",
    "Campeonato Gaúcho", "Campeonato Mineiro", "Campeonato Paulista",
]

ALL_CHAMPIONSHIPS = TIER1_CHAMPIONSHIPS + BRAZIL_CHAMPIONSHIPS
