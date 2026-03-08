"""Report Generator — produces formatted reports for WhatsApp/Telegram."""

import logging
from datetime import datetime

from analysis.odds_analyzer import OddsAnalyzer, EventAnalysis, MarketAnalysis

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates formatted reports in the exact WhatsApp/Telegram format."""

    def __init__(self, analyzer: OddsAnalyzer):
        self.analyzer = analyzer

    def generate_full_report(self, report_date: str = "", collection_time: str = "") -> str:
        """
        Generate the complete report in the specified format.

        Args:
            report_date: Date string (DD/MM/YYYY). Defaults to today.
            collection_time: Time of data collection (HH:MM). Defaults to now.
        """
        if not report_date:
            report_date = datetime.now().strftime("%d/%m/%Y")
        if not collection_time:
            collection_time = datetime.now().strftime("%H:%M")

        parts = [
            self._header(report_date),
            self._highlights(),
            self._pre_match_analysis(),
            self._live_games(),
            self._executive_summary(),
            self._strategic_recommendations(),
            self._footer(collection_time, report_date),
        ]

        return "\n".join(parts)

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
        lines.append(f"_Relatório completo disponível no dashboard._")

        return "\n".join(lines)

    def _header(self, report_date: str) -> str:
        return (
            f"📊 *ANÁLISE DE ODDS — {report_date}* 📊\n"
            f"*Relatório de inteligência competitiva — ROP Soluções / DP Sports*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

    def _highlights(self) -> str:
        """Generate the highlights section."""
        lines = [
            "\n🎯 *DESTAQUES DO DIA*",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        opportunities = self.analyzer.get_opportunities()
        attention = self.analyzer.get_attention_points()

        if opportunities:
            top = opportunities[:3]
            games_text = ", ".join(
                f"{a.home_team} vs {a.away_team} ({a.market}: {a.rop_odd:.2f} vs. média {a.market_avg:.2f})"
                for a in top
            )
            lines.append(
                f"\nA ROP se destaca hoje com odds superiores à média em: {games_text}. "
                f"Esses são diferenciais competitivos que devem ser mantidos."
            )

        if attention:
            top = attention[:3]
            games_text = ", ".join(
                f"{a.home_team} vs {a.away_team} ({a.market}: {a.rop_odd:.2f} vs. média {a.market_avg:.2f})"
                for a in top
            )
            lines.append(
                f"\nEm contrapartida, exigem atenção: {games_text}. "
                f"Revisão recomendada para manter competitividade."
            )

        if not opportunities and not attention:
            lines.append(
                "\nTodas as odds da ROP estão dentro da faixa de ±3% da média dos concorrentes. "
                "Posicionamento equilibrado e competitivo hoje."
            )

        return "\n".join(lines)

    def _pre_match_analysis(self) -> str:
        """Generate the pre-match analysis section."""
        lines = [
            "\n━━━━━━━━━━━━━━━━━━━━━━",
            "⚽ *ANÁLISE PRÉ-JOGO*",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        current_champ = ""
        for event in self.analyzer.events:
            # Championship header
            if event.championship != current_champ:
                current_champ = event.championship
                lines.append(f"\n🏆 *{current_champ or 'Campeonato não identificado'}*")

            lines.append(self._format_event(event))

        return "\n".join(lines)

    def _format_event(self, event: EventAnalysis) -> str:
        """Format a single event block."""
        time_str = f" | {event.match_time} BRT" if event.match_time else ""
        lines = [
            f"\n🆚 *{event.home_team} vs {event.away_team}*{time_str}",
        ]

        # 1X2 Market
        m_home = event.markets.get("1x2_home")
        m_draw = event.markets.get("1x2_draw")
        m_away = event.markets.get("1x2_away")

        if m_home or m_draw or m_away:
            lines.append("*Resultado 1X2:*")

            rop_home = f"*{m_home.rop_odd:.2f}*" if m_home and m_home.rop_odd else "-"
            rop_draw = f"*{m_draw.rop_odd:.2f}*" if m_draw and m_draw.rop_odd else "-"
            rop_away = f"*{m_away.rop_odd:.2f}*" if m_away and m_away.rop_odd else "-"
            lines.append(f"• *ROP:* {rop_home} | {rop_draw} | {rop_away} {event.overall_emoji}")

            avg_home = f"{m_home.avg_competitors:.2f}" if m_home and m_home.avg_competitors else "-"
            avg_draw = f"{m_draw.avg_competitors:.2f}" if m_draw and m_draw.avg_competitors else "-"
            avg_away = f"{m_away.avg_competitors:.2f}" if m_away and m_away.avg_competitors else "-"
            lines.append(f"• Média Conc.: {avg_home} | {avg_draw} | {avg_away}")

            best_parts = []
            for m, label in [(m_home, "Casa"), (m_draw, "Empate"), (m_away, "Fora")]:
                if m and m.best_odd:
                    best_parts.append(f"{m.best_odd:.2f} ({m.best_odd_site})")
                else:
                    best_parts.append("-")
            lines.append(f"• Melhor Odd: {' | '.join(best_parts)}")

        # Secondary markets
        btts_yes = event.markets.get("btts_yes")
        btts_no = event.markets.get("btts_no")
        over_25 = event.markets.get("over_25")
        under_25 = event.markets.get("under_25")

        has_secondary = any(
            m and m.rop_odd is not None
            for m in [btts_yes, btts_no, over_25, under_25]
        )

        if has_secondary:
            lines.append("*Outros Mercados (ROP):*")

            if btts_yes or btts_no:
                yes_val = f"*{btts_yes.rop_odd:.2f}*" if btts_yes and btts_yes.rop_odd else "-"
                no_val = f"*{btts_no.rop_odd:.2f}*" if btts_no and btts_no.rop_odd else "-"
                lines.append(f"• Ambos Marcam: Sim {yes_val} / Não {no_val}")

            if over_25 or under_25:
                over_val = f"*{over_25.rop_odd:.2f}*" if over_25 and over_25.rop_odd else "-"
                under_val = f"*{under_25.rop_odd:.2f}*" if under_25 and under_25.rop_odd else "-"
                lines.append(f"• Mais/Menos 2.5: Mais {over_val} / Menos {under_val}")
        else:
            lines.append("*Outros Mercados (ROP):*")
            lines.append("• Ambos Marcam: Sem dados disponíveis")
            lines.append("• Mais/Menos 2.5: Sem dados disponíveis")

        # Analysis comment
        comment = self._generate_comment(event)
        lines.append(f"\n📌 *Análise:* {comment}")
        lines.append("---")

        return "\n".join(lines)

    def _generate_comment(self, event: EventAnalysis) -> str:
        """Generate a 1-2 line analytical comment for an event."""
        alerts_above = []
        alerts_below = []

        for key, market in event.markets.items():
            if market.status == "above" and market.rop_odd:
                alerts_above.append((market.market_name, market.deviation_pct))
            elif market.status == "below" and market.rop_odd:
                alerts_below.append((market.market_name, market.deviation_pct))

        if alerts_above and not alerts_below:
            markets = ", ".join(f"{m} (+{d:.1f}%)" for m, d in alerts_above)
            return f"ROP acima da média em {markets}. Diferencial competitivo positivo."

        if alerts_below and not alerts_above:
            markets = ", ".join(f"{m} ({d:.1f}%)" for m, d in alerts_below)
            return f"ROP abaixo da média em {markets}. Revisão recomendada."

        if alerts_above and alerts_below:
            above = ", ".join(m for m, _ in alerts_above)
            below = ", ".join(m for m, _ in alerts_below)
            return f"Mercado misto: acima em {above}, abaixo em {below}."

        return "Posicionamento equilibrado. Odds dentro da faixa de ±3% da média."

    def _live_games(self) -> str:
        """Generate live games section."""
        return (
            "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔴 *JOGOS AO VIVO*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Nenhum jogo ao vivo no momento da coleta."
        )

    def _executive_summary(self) -> str:
        """Generate executive summary."""
        lines = [
            "\n━━━━━━━━━━━━━━━━━━━━━━",
            "📋 *RESUMO EXECUTIVO*",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        opportunities = self.analyzer.get_opportunities()
        attention = self.analyzer.get_attention_points()
        stats = self.analyzer.get_summary_stats()

        lines.append("\n*✅ Oportunidades — ROP acima da média:*")
        if opportunities:
            seen = set()
            for a in opportunities:
                key = f"{a.home_team} vs {a.away_team}"
                if key not in seen:
                    lines.append(f"• {key}: {a.market} ({a.rop_odd:.2f})")
                    seen.add(key)
        else:
            lines.append("• Nenhuma oportunidade identificada nesta coleta.")

        lines.append("\n*⚠️ Pontos de Atenção — ROP abaixo da média:*")
        if attention:
            seen = set()
            for a in attention:
                key = f"{a.home_team} vs {a.away_team}"
                if key not in seen:
                    lines.append(f"• {key}: {a.market} ({a.rop_odd:.2f} vs. média {a.market_avg:.2f})")
                    seen.add(key)
        else:
            lines.append("• Nenhum ponto de atenção nesta coleta.")

        lines.append("\n*📊 Cobertura de Jogos:*")
        lines.append(f"• ROP cobriu {stats['rop_covered']} de {stats['total_events']} jogos analisados hoje.")

        missing = stats["championships_missing"]
        if missing:
            lines.append(f"• Campeonatos sem cobertura da ROP: {', '.join(missing)}.")
        else:
            lines.append("• Campeonatos sem cobertura da ROP: Nenhum.")

        return "\n".join(lines)

    def _strategic_recommendations(self) -> str:
        """Generate strategic recommendations."""
        lines = [
            "\n━━━━━━━━━━━━━━━━━━━━━━",
            "💡 *RECOMENDAÇÕES ESTRATÉGICAS*",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]

        attention = self.analyzer.get_attention_points()
        opportunities = self.analyzer.get_opportunities()

        # Recommendation 1: Immediate adjustment
        if attention:
            worst = max(attention, key=lambda a: abs(a.deviation_pct))
            lines.append(
                f"\n1. *Ajuste Imediato:* Revisar {worst.market} em "
                f"{worst.home_team} vs {worst.away_team} — "
                f"ROP {worst.rop_odd:.2f} está {abs(worst.deviation_pct):.1f}% abaixo "
                f"da média ({worst.market_avg:.2f})."
            )
        else:
            lines.append("\n1. *Ajuste Imediato:* Nenhum ajuste urgente necessário hoje.")

        # Recommendation 2: Maintain position
        if opportunities:
            best = max(opportunities, key=lambda a: a.deviation_pct)
            lines.append(
                f"2. *Manter Posição:* {best.market} em "
                f"{best.home_team} vs {best.away_team} — "
                f"ROP oferece {best.rop_odd:.2f}, {best.deviation_pct:.1f}% acima da média. "
                f"Manter este diferencial competitivo."
            )
        else:
            lines.append("2. *Manter Posição:* Posicionamento geral equilibrado. Manter odds atuais.")

        # Recommendation 3: Observation
        stats = self.analyzer.get_summary_stats()
        total_alerts = stats["alerts_above"] + stats["alerts_below"]
        lines.append(
            f"3. *Observação:* {total_alerts} alertas gerados nesta coleta. "
            f"Monitorar evolução das odds ao vivo nos jogos da tarde."
        )

        return "\n".join(lines)

    def _footer(self, collection_time: str, report_date: str) -> str:
        return (
            f"\n---\n"
            f"_Dados coletados às {collection_time} BRT — {report_date}_"
        )
