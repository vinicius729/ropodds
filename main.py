"""
ROP Odds Mapping System — Main Entry Point

Automated odds comparison system for ROP Soluções / DP Sports.
Scrapes odds from multiple betting sites, analyzes deviations,
and sends reports + alerts via Telegram.

Usage:
    python main.py                  # Run the scheduler (daily at configured times)
    python main.py --run-now        # Run a single analysis immediately
    python main.py --manual         # Input data manually and generate report
    python main.py --test-telegram  # Test Telegram connection
    python main.py --dashboard      # Start only the web dashboard
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import SCHEDULE_TIMES, TIMEZONE
from scrapers.scraper_manager import ScraperManager
from scrapers.manual_input import parse_manual_input
from analysis.odds_analyzer import OddsAnalyzer
from analysis.report_generator import ReportGenerator
from telegram_bot.bot import TelegramNotifier
from models import init_db, ScrapeSession, OddsRecord, Alert, DailyReport

# Brasilia timezone (UTC-3)
BRT = timezone(timedelta(hours=-3))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/ropodds.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ropodds")


def now_brt() -> datetime:
    """Get current datetime in Brasilia timezone."""
    return datetime.now(BRT)


class ROPOddsSystem:
    """Main system orchestrator."""

    def __init__(self):
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

        self.engine, self.Session = init_db()
        self.scraper_manager = ScraperManager()
        self.analyzer = OddsAnalyzer()
        self.telegram = TelegramNotifier()

    async def run_analysis(self, target_date: str | None = None) -> str:
        """Run a complete analysis cycle: scrape → analyze → report → alert."""
        current_time = now_brt()

        if target_date is None:
            target_date = current_time.strftime("%Y-%m-%d")

        session = self.Session()
        db_session = ScrapeSession(started_at=current_time, status="running")
        session.add(db_session)
        session.commit()

        try:
            # 1. Scrape all sites
            logger.info(f"=== Starting analysis for {target_date} at {current_time.strftime('%H:%M')} BRT ===")
            all_data = await self.scraper_manager.scrape_all(target_date)

            # 2. Save raw data to DB
            total_records = 0
            for site_name, odds_list in all_data.items():
                for odds in odds_list:
                    record = OddsRecord(
                        session_id=db_session.id,
                        championship=odds.championship,
                        home_team=odds.home_team,
                        away_team=odds.away_team,
                        match_time=odds.match_time,
                        match_date=odds.match_date,
                        site_name=odds.site_name,
                        site_type=odds.site_type,
                        odd_home=odds.odd_home,
                        odd_draw=odds.odd_draw,
                        odd_away=odds.odd_away,
                        odd_btts_yes=odds.odd_btts_yes,
                        odd_btts_no=odds.odd_btts_no,
                        odd_over_25=odds.odd_over_25,
                        odd_under_25=odds.odd_under_25,
                    )
                    session.add(record)
                    total_records += 1

            # 3. Analyze
            events = self.analyzer.analyze(all_data)

            # 4. Generate report (always in BRT)
            report_gen = ReportGenerator(self.analyzer)
            report_date = datetime.strptime(target_date, "%Y-%m-%d").strftime("%d/%m/%Y")
            collection_time = now_brt().strftime("%H:%M")
            full_report = report_gen.generate_full_report(report_date, collection_time)

            # 5. Save report to DB
            stats = self.analyzer.get_summary_stats()
            db_report = DailyReport(
                session_id=db_session.id,
                report_date=target_date,
                report_time=collection_time,
                report_text=full_report,
                total_events=stats["total_events"],
                alerts_above=stats["alerts_above"],
                alerts_below=stats["alerts_below"],
            )
            session.add(db_report)

            # 6. Save alerts to DB
            for alert in self.analyzer.alerts:
                db_alert = Alert(
                    session_id=db_session.id,
                    championship=alert.championship,
                    home_team=alert.home_team,
                    away_team=alert.away_team,
                    match_time=alert.match_time,
                    market=alert.market,
                    rop_odd=alert.rop_odd,
                    market_avg=alert.market_avg,
                    deviation_pct=alert.deviation_pct,
                    alert_type=alert.alert_type,
                    severity="high" if abs(alert.deviation_pct) > 5 else "medium",
                )
                session.add(db_alert)

            # 7. Send to Telegram
            try:
                # Send alert first (short message)
                alert_msg = report_gen.generate_alert_message()
                if alert_msg:
                    await self.telegram.send_alert(alert_msg)

                # Then send full report
                await self.telegram.send_report(full_report)
                logger.info("Reports sent to Telegram successfully")
            except Exception as e:
                logger.error(f"Telegram sending failed: {e}")

            # Update session
            db_session.status = "completed"
            db_session.finished_at = now_brt()
            db_session.total_events = stats["total_events"]
            db_session.total_alerts = stats["alerts_above"] + stats["alerts_below"]
            session.commit()

            logger.info(
                f"=== Analysis complete: {stats['total_events']} events, "
                f"{stats['alerts_above']} above, {stats['alerts_below']} below ==="
            )
            return full_report

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            db_session.status = "failed"
            session.commit()
            raise
        finally:
            session.close()

    async def run_manual_analysis(self, input_text: str, target_date: str = "") -> str:
        """Run analysis from manually input data."""
        if not target_date:
            target_date = now_brt().strftime("%Y-%m-%d")

        records = parse_manual_input(input_text, target_date)

        # Group by site
        all_data: dict[str, list] = {}
        for record in records:
            if record.site_name not in all_data:
                all_data[record.site_name] = []
            all_data[record.site_name].append(record)

        # Analyze
        events = self.analyzer.analyze(all_data)
        report_gen = ReportGenerator(self.analyzer)
        report_date = datetime.strptime(target_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        collection_time = now_brt().strftime("%H:%M")
        report = report_gen.generate_full_report(report_date, collection_time)

        # Send to Telegram
        try:
            alert_msg = report_gen.generate_alert_message()
            if alert_msg:
                await self.telegram.send_alert(alert_msg)
            await self.telegram.send_report(report)
        except Exception as e:
            logger.warning(f"Telegram failed: {e}")

        return report

    def start_scheduler(self):
        """Start the APScheduler with configured times in BRT."""
        scheduler = AsyncIOScheduler(timezone=TIMEZONE)

        for time_str in SCHEDULE_TIMES:
            hour, minute = time_str.strip().split(":")
            trigger = CronTrigger(hour=int(hour), minute=int(minute), timezone=TIMEZONE)
            scheduler.add_job(
                self.run_analysis,
                trigger=trigger,
                id=f"analysis_{time_str}",
                name=f"Odds Analysis at {time_str} BRT",
                misfire_grace_time=600,  # 10 min grace period
                max_instances=1,
            )
            logger.info(f"Scheduled analysis at {time_str} BRT ({TIMEZONE})")

        scheduler.start()
        logger.info(
            f"Scheduler started. Analysis times: "
            f"{', '.join(SCHEDULE_TIMES)} ({TIMEZONE})"
        )
        return scheduler


async def main():
    parser = argparse.ArgumentParser(description="ROP Odds Mapping System")
    parser.add_argument("--run-now", action="store_true", help="Run analysis immediately")
    parser.add_argument("--manual", action="store_true", help="Input data manually")
    parser.add_argument("--manual-file", type=str, help="Path to manual data file")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--test-telegram", action="store_true", help="Test Telegram connection")
    parser.add_argument("--dashboard", action="store_true", help="Start web dashboard only")
    args = parser.parse_args()

    system = ROPOddsSystem()

    if args.test_telegram:
        result = await system.telegram.test_connection()
        print("✅ Telegram conectado!" if result else "❌ Falha na conexão Telegram")
        return

    if args.dashboard:
        from dashboard.app import create_app, set_system_instance
        from config.settings import DASHBOARD_HOST, DASHBOARD_PORT
        app = create_app(system.Session)
        set_system_instance(system)
        app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=True)
        return

    if args.manual or args.manual_file:
        if args.manual_file:
            with open(args.manual_file, "r", encoding="utf-8") as f:
                input_text = f.read()
        else:
            print("Cole os dados de odds abaixo (pressione Ctrl+D quando terminar):")
            input_text = sys.stdin.read()

        report = await system.run_manual_analysis(input_text, args.date or "")
        print("\n" + "=" * 50)
        print(report)
        return

    if args.run_now:
        report = await system.run_analysis(args.date)
        print(report)
        return

    # Default: start scheduler + dashboard (cloud mode)
    logger.info(f"Starting ROP Odds System at {now_brt().strftime('%d/%m/%Y %H:%M')} BRT")
    scheduler = system.start_scheduler()

    from dashboard.app import create_app, set_system_instance
    from config.settings import DASHBOARD_HOST, DASHBOARD_PORT

    app = create_app(system.Session)
    set_system_instance(system)  # Wire up webhook endpoints

    logger.info(f"Dashboard: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    logger.info(f"Input form: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}/input")
    logger.info("System running. Press Ctrl+C to stop.")

    # Run Flask in a thread
    import threading
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host=DASHBOARD_HOST,
            port=DASHBOARD_PORT,
            debug=False,
            use_reloader=False,
        ),
        daemon=True,
    )
    flask_thread.start()

    # Keep the async loop running for APScheduler
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
