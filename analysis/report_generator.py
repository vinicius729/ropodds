"""Report Generator — produces formatted reports matching the exact template."""

import logging
from datetime import datetime

from analysis.odds_analyzer import OddsAnalyzer, EventAnalysis, MarketAnalysis

logger = logging.getLogger(__name__)

# Championship flag emojis
CHAMPIONSHIP_FLAGS = {
    # Europe
    "bundesliga": "🇩🇪",
    "laliga": "🇪🇸",
    "la liga": "🇪🇸",
    "serie a": "🇮🇹",
    "ligue 1": "🇫🇷",
    "premier league": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "eredivisie": "🇳🇱",
    "primeira liga": "🇵🇹",
    "fa cup": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "champions league": "🇪🇺",
    "europa league": "🇪🇺",
    "conference league": "🇪🇺",
    # Brazil
    "brasileirão": "🇧🇷",
    "brasileirao": "🇧🇷",
    "série a": "🇧🇷",
    "série b": "🇧🇷",
    "carioca": "🇧🇷",
    "paulista": "🇧🇷",
    "mineiro": "🇧🇷",
    "gaúcho": "🇧🇷",
    "gaucho": "🇧🇷",
    "baiano": "🇧🇷",
    "catarinense": "🇧🇷",
    "cearense": "🇧🇷",
    "pernambucano": "🇧🇷",
    "paraense": "🇧🇷",
    "copa do brasil": "🇧🇷",
    # South America
    "libertadores": "🌎",
    "sul-americana": "🌎",
    "copa america": "🌎",
    # Other
    "mls": "🇺🇸",
}

# Alert threshold (percentage)
ALERT_THRESHOLD = 2.0


def _get_flag(championship: str) -> str:
    """Get flag emoji for a championship."""
    lower = championship.lower()
    # Check for "Brasil - Campeonato X" format
    if lower.startswith("brasil"):
        for kw, flag in CHAMPIONSHIP_FLAGS.items():
            if kw in lower:
                return flag
        return "🇧🇷"
    for kw, flag in CHAMPIONSHIP_FLAGS.items():
        if kw in lower:
            return flag
    # Try country prefix
    country_flags = {
        "itália": "🇮🇹", "espanha": "🇪🇸", "alemanha": "🇩🇪",
        "frança": "🇫🇷", "portugal": "🇵🇹", "holanda": "🇳🇱",
        "inglaterra": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "méxico": "🇲🇽", "argentina": "🇦🇷",
        "chile": "🇨🇱", "uruguai": "🇺🇾", "paraguai": "🇵🇾",
        "colômbia": "🇨🇴", "peru": "🇵🇪", "equador": "🇪🇨",
        "turquia": "🇹🇷", "grécia": "🇬🇷", "bélgica": "🇧🇪",
        "estados unidos": "🇺🇸", "japão": "🇯🇵", "coreia": "🇰🇷",
    }
    for kw, flag in country_flags.items():
        if kw in lower:
            return flag
    return "⚽"


def _fmt_odd(val) -> str:
    """Format an odd value."""
    if val is None:
        return "—"
    return f"{val:.2f}"


def _fmt_pct(rop_val, avg_val) -> str:
    """Format ROP vs Market percentage."""
    if rop_val is None or avg_val is None or avg_val == 0:
        return "—"
    pct = ((rop_val - avg_val) / avg_val) * 100
    if abs(pct) < 0.05:
        return "—"
    sign = "+" if pct > 0 else ""
    result = f"{sign}{pct:.1f}%"
    if pct > ALERT_THRESHOLD:
        result += " ✅"
    elif pct < -ALERT_THRESHOLD:
        result += " ⚠️"
    return result


class ReportGenerator:
    """Generates formatted reports in the exact Telegram template format."""

    def __init__(self, analyzer: OddsAnalyzer):
        self.analyzer = analyzer

    def generate_full_report(self, report_date: str = "", collection_time: str = "") -> str:
        if not report_date:
            report_date = datetime.now().strftime("%d/%m/%Y")
        if not collection_time:
            collection_time = datetime.now().strftime("%H:%M")

        parts = [
            self._header(report_date, collection_time),
            self._highlights(),
            self._championship_sections(),
            self._legend(),
            self._footer(report_date, collection_time),
        ]

        return "\n".join(p for p in parts if p)

    def generate_alert_message(self) -> str:
        """Generate a short alert message for immediate Telegram notifications."""
        alerts_above = self.analyzer.get_opportunities()
        alerts_below = self.analyzer.get_attention_points()

        if not alerts_above and not alerts_below:
            return ""

        lines = ["🚨 *ALERTA DE ODDS — ROP/DP Sports* 🚨", ""]

        if alerts_above:
            lines.append("✅ *ROP ACIMA da média:*")
            for a in alerts_above[:5]:
                lines.append(
                    f"• {a.home_team} vs {a.away_team} | "
                    f"{a.market}: *{a.rop_odd:.2f}* (média {a.market_avg:.2f}, +{a.deviation_pct:.1f}%)"
                )
            lines.append("")

        if alerts_below:
            lines.append("⚠️ *ROP ABAIXO da média:*")
            for a in alerts_below[:5]:
                lines.append(
                    f"• {a.home_team} vs {a.away_team} | "
                    f"{a.market}: *{a.rop_odd:.2f}* (média {a.market_avg:.2f}, {a.deviation_pct:.1f}%)"
                )
            lines.append("")

        lines.append(f"📊 Total: {len(alerts_above)} acima | {len(alerts_below)} abaixo")
        return "\n".join(lines)

    def _header(self, report_date: str, collection_time: str) -> str:
        # Collect monitored site names
        site_names = set()
        for event in self.analyzer.events:
            for market in event.markets.values():
                if market.rop_odd is not None:
                    site_names.add("ROP/DP Sports")
                for sn in market.competitor_odds:
                    site_names.add(sn)

        # Order: ROP first, then alphabetical
        ordered = []
        if "ROP/DP Sports" in site_names:
            ordered.append("ROP/DP Sports")
            site_names.discard("ROP/DP Sports")
        ordered.extend(sorted(site_names))
        sites_str = ", ".join(ordered) if ordered else "—"

        return (
            f"# 📊 RELATÓRIO COMPETITIVO DE ODDS — {report_date}\n"
            f"**Gerado em:** {report_date} às {collection_time} BRT\n"
            f"**Sites monitorados:** {sites_str}\n"
            f"**Mercados analisados:** Resultado 1X2 | Mais/Menos 1.5 Gols | Mais/Menos 2.5 Gols | Ambos Marcam\n"
            f"---"
        )

    def _highlights(self) -> str:
        """Generate DESTAQUES DO DIA section."""
        lines = ["## 🎯 DESTAQUES DO DIA"]

        # Find all markets where ROP is above average by > ALERT_THRESHOLD %
        highlights_above = []
        highlights_below = []

        for event in self.analyzer.events:
            for key, market in event.markets.items():
                if market.rop_odd is None or market.avg_competitors is None:
                    continue
                if market.avg_competitors == 0:
                    continue
                pct = ((market.rop_odd - market.avg_competitors) / market.avg_competitors) * 100
                item = (event, market, pct)
                if pct > ALERT_THRESHOLD:
                    highlights_above.append(item)
                elif pct < -ALERT_THRESHOLD:
                    highlights_below.append(item)

        # Sort by deviation descending
        highlights_above.sort(key=lambda x: -x[2])
        highlights_below.sort(key=lambda x: x[2])

        if highlights_above:
            lines.append("### Odds ROP acima do mercado:")
            for event, market, pct in highlights_above:
                market_label = self._market_label(market.market_name)
                lines.append(
                    f"- ✅ **{event.home_team} vs {event.away_team}** — "
                    f"{market_label}: ROP {market.rop_odd:.2f} vs Média {market.avg_competitors:.2f} "
                    f"(+{pct:.1f}%)"
                )

        if highlights_below:
            lines.append("### Odds ROP abaixo do mercado:")
            for event, market, pct in highlights_below:
                market_label = self._market_label(market.market_name)
                lines.append(
                    f"- ⚠️ **{event.home_team} vs {event.away_team}** — "
                    f"{market_label}: ROP {market.rop_odd:.2f} vs Média {market.avg_competitors:.2f} "
                    f"({pct:.1f}%)"
                )

        if not highlights_above and not highlights_below:
            lines.append("Todas as odds da ROP estão dentro da faixa de ±2% da média dos concorrentes.")

        lines.append("---")
        return "\n".join(lines)

    def _championship_sections(self) -> str:
        """Generate all championship sections with event tables."""
        # Group events by championship
        champ_events: dict[str, list[EventAnalysis]] = {}
        for event in self.analyzer.events:
            champ = event.championship or "Outros"
            if champ not in champ_events:
                champ_events[champ] = []
            champ_events[champ].append(event)

        # Sort championships
        sections = []
        for champ in sorted(champ_events.keys()):
            events = champ_events[champ]
            # Sort by match time
            events.sort(key=lambda e: e.match_time or "99:99")

            flag = _get_flag(champ)
            section_lines = [f"## {flag} {champ}"]

            for event in events:
                section_lines.append(self._format_event_table(event))
                section_lines.append("---")

            sections.append("\n".join(section_lines))

        return "\n".join(sections)

    def _format_event_table(self, event: EventAnalysis) -> str:
        """Format a single event with full odds table matching the template."""
        time_str = f" | {event.match_time} BRT" if event.match_time else ""
        lines = [f"### ⚽ {event.home_team} vs {event.away_team}{time_str}"]

        # Get 1X2 markets
        m_home = event.markets.get("1x2_home")
        m_draw = event.markets.get("1x2_draw")
        m_away = event.markets.get("1x2_away")

        if m_home or m_draw or m_away:
            lines.append("**RESULTADO 1X2**")

            # Collect all competitor site names across all markets
            all_sites = set()
            for m in [m_home, m_draw, m_away]:
                if m:
                    all_sites.update(m.competitor_odds.keys())
            site_list = sorted(all_sites)

            # Table header
            lines.append("| Site | Casa | Empate | Fora |")
            lines.append("|:-----|:----:|:------:|:----:|")

            # ROP row
            rop_h = _fmt_odd(m_home.rop_odd if m_home else None)
            rop_d = _fmt_odd(m_draw.rop_odd if m_draw else None)
            rop_a = _fmt_odd(m_away.rop_odd if m_away else None)
            lines.append(f"| **ROP/DP Sports** | **{rop_h}** | **{rop_d}** | **{rop_a}** |")

            # Competitor rows
            for site in site_list:
                h = _fmt_odd(m_home.competitor_odds.get(site) if m_home else None)
                d = _fmt_odd(m_draw.competitor_odds.get(site) if m_draw else None)
                a = _fmt_odd(m_away.competitor_odds.get(site) if m_away else None)
                lines.append(f"| {site} | {h} | {d} | {a} |")

            # Average row
            avg_h = _fmt_odd(m_home.avg_competitors if m_home else None)
            avg_d = _fmt_odd(m_draw.avg_competitors if m_draw else None)
            avg_a = _fmt_odd(m_away.avg_competitors if m_away else None)
            lines.append(f"| **Média Concorrentes** | **{avg_h}** | **{avg_d}** | **{avg_a}** |")

            # ROP vs Market row
            pct_h = _fmt_pct(
                m_home.rop_odd if m_home else None,
                m_home.avg_competitors if m_home else None
            )
            pct_d = _fmt_pct(
                m_draw.rop_odd if m_draw else None,
                m_draw.avg_competitors if m_draw else None
            )
            pct_a = _fmt_pct(
                m_away.rop_odd if m_away else None,
                m_away.avg_competitors if m_away else None
            )
            lines.append(f"| **ROP vs Mercado** | **{pct_h}** | **{pct_d}** | **{pct_a}** |")

        # Goals markets table
        m_over15 = event.markets.get("over_15")
        m_under15 = event.markets.get("under_15")
        m_over25 = event.markets.get("over_25")
        m_under25 = event.markets.get("under_25")
        m_btts_yes = event.markets.get("btts_yes")
        m_btts_no = event.markets.get("btts_no")

        has_goals = any(
            m and m.rop_odd is not None
            for m in [m_over15, m_under15, m_over25, m_under25, m_btts_yes, m_btts_no]
        )

        if has_goals:
            lines.append("**MERCADOS DE GOLS**")
            lines.append("| Mercado | Mais | Menos |")
            lines.append("|:--------|:----:|:-----:|")

            over15 = _fmt_odd(m_over15.rop_odd if m_over15 else None)
            under15 = _fmt_odd(m_under15.rop_odd if m_under15 else None)
            lines.append(f"| **Mais/Menos 1.5 Gols (ROP)** | {over15} | {under15} |")

            over25 = _fmt_odd(m_over25.rop_odd if m_over25 else None)
            under25 = _fmt_odd(m_under25.rop_odd if m_under25 else None)
            lines.append(f"| **Mais/Menos 2.5 Gols (ROP)** | {over25} | {under25} |")

            btts_y = _fmt_odd(m_btts_yes.rop_odd if m_btts_yes else None)
            btts_n = _fmt_odd(m_btts_no.rop_odd if m_btts_no else None)
            lines.append(f"| **Ambos Marcam (ROP)** | Sim: {btts_y} | Não: {btts_n} |")

        return "\n".join(lines)

    def _market_label(self, market_name: str) -> str:
        """Convert internal market name to display label."""
        labels = {
            "1X2 - Casa": "Casa",
            "1X2 - Empate": "Empate",
            "1X2 - Fora": "Fora",
            "Ambos Marcam - Sim": "Ambos Marcam Sim",
            "Ambos Marcam - Não": "Ambos Marcam Não",
            "Mais 2.5 Gols": "Mais 2.5",
            "Menos 2.5 Gols": "Menos 2.5",
            "Mais 1.5 Gols": "Mais 1.5",
            "Menos 1.5 Gols": "Menos 1.5",
        }
        return labels.get(market_name, market_name)

    def _legend(self) -> str:
        return (
            "## 📋 LEGENDA\n"
            "| Símbolo | Significado |\n"
            "|:-------:|:-----------|\n"
            "| ✅ | Odd da ROP mais de 2% acima da média dos concorrentes |\n"
            "| ⚠️ | Odd da ROP mais de 2% abaixo da média dos concorrentes |\n"
            "| — | Dado não disponível no site |\n"
            "> **Nota:** Dados coletados diretamente dos sites em tempo real. "
            "Odds podem sofrer alterações até o início dos jogos."
        )

    def _footer(self, report_date: str, collection_time: str) -> str:
        return f"*Relatório gerado automaticamente em {report_date} às {collection_time} BRT*"
