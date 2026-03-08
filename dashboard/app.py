"""Flask web dashboard for the ROP Odds Mapping System."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, jsonify, request

from config.settings import DASHBOARD_SECRET_KEY, API_KEY
from models import ScrapeSession, OddsRecord, Alert, DailyReport

logger = logging.getLogger(__name__)

# Reference to the system instance — set by main.py
_system_instance = None


def set_system_instance(system):
    global _system_instance
    _system_instance = system


def require_api_key(f):
    """Decorator to require API key for webhook endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"error": "Unauthorized. Provide X-API-Key header."}), 401
        return f(*args, **kwargs)
    return decorated


def create_app(SessionFactory) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = DASHBOARD_SECRET_KEY

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/dashboard")
    def api_dashboard():
        """Main dashboard data."""
        session = SessionFactory()
        try:
            # Recent sessions
            sessions = (
                session.query(ScrapeSession)
                .order_by(ScrapeSession.started_at.desc())
                .limit(10)
                .all()
            )

            # Today's stats
            today = datetime.now().strftime("%Y-%m-%d")
            today_reports = (
                session.query(DailyReport)
                .filter(DailyReport.report_date == today)
                .all()
            )

            today_alerts = (
                session.query(Alert)
                .join(ScrapeSession)
                .filter(DailyReport.report_date == today)
                .all()
            )

            return jsonify({
                "sessions": [
                    {
                        "id": s.id,
                        "started_at": s.started_at.isoformat() if s.started_at else None,
                        "status": s.status,
                        "total_events": s.total_events,
                        "total_alerts": s.total_alerts,
                    }
                    for s in sessions
                ],
                "today": {
                    "total_reports": len(today_reports),
                    "total_events": sum(r.total_events for r in today_reports),
                    "alerts_above": sum(r.alerts_above for r in today_reports),
                    "alerts_below": sum(r.alerts_below for r in today_reports),
                },
            })
        finally:
            session.close()

    @app.route("/api/reports")
    def api_reports():
        """List all reports."""
        session = SessionFactory()
        try:
            date_filter = request.args.get("date")
            query = session.query(DailyReport).order_by(DailyReport.created_at.desc())

            if date_filter:
                query = query.filter(DailyReport.report_date == date_filter)

            reports = query.limit(30).all()

            return jsonify([
                {
                    "id": r.id,
                    "date": r.report_date,
                    "time": r.report_time,
                    "total_events": r.total_events,
                    "alerts_above": r.alerts_above,
                    "alerts_below": r.alerts_below,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in reports
            ])
        finally:
            session.close()

    @app.route("/api/reports/<int:report_id>")
    def api_report_detail(report_id):
        """Get a specific report."""
        session = SessionFactory()
        try:
            report = session.query(DailyReport).get(report_id)
            if not report:
                return jsonify({"error": "Report not found"}), 404

            return jsonify({
                "id": report.id,
                "date": report.report_date,
                "time": report.report_time,
                "text": report.report_text,
                "total_events": report.total_events,
                "alerts_above": report.alerts_above,
                "alerts_below": report.alerts_below,
            })
        finally:
            session.close()

    @app.route("/api/alerts")
    def api_alerts():
        """List alerts with optional filters."""
        session = SessionFactory()
        try:
            query = session.query(Alert).order_by(Alert.created_at.desc())

            alert_type = request.args.get("type")
            if alert_type:
                query = query.filter(Alert.alert_type == alert_type)

            date_filter = request.args.get("date")
            if date_filter:
                query = query.join(ScrapeSession).filter(
                    ScrapeSession.started_at >= datetime.strptime(date_filter, "%Y-%m-%d"),
                    ScrapeSession.started_at < datetime.strptime(date_filter, "%Y-%m-%d") + timedelta(days=1),
                )

            alerts = query.limit(100).all()

            return jsonify([
                {
                    "id": a.id,
                    "championship": a.championship,
                    "home_team": a.home_team,
                    "away_team": a.away_team,
                    "match_time": a.match_time,
                    "market": a.market,
                    "rop_odd": a.rop_odd,
                    "market_avg": a.market_avg,
                    "deviation_pct": a.deviation_pct,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in alerts
            ])
        finally:
            session.close()

    @app.route("/api/odds/history")
    def api_odds_history():
        """Odds history for a specific event or market."""
        session = SessionFactory()
        try:
            home = request.args.get("home", "")
            away = request.args.get("away", "")

            query = session.query(OddsRecord).order_by(OddsRecord.collected_at.desc())

            if home:
                query = query.filter(OddsRecord.home_team.ilike(f"%{home}%"))
            if away:
                query = query.filter(OddsRecord.away_team.ilike(f"%{away}%"))

            records = query.limit(200).all()

            return jsonify([
                {
                    "site_name": r.site_name,
                    "site_type": r.site_type,
                    "championship": r.championship,
                    "home_team": r.home_team,
                    "away_team": r.away_team,
                    "odd_home": r.odd_home,
                    "odd_draw": r.odd_draw,
                    "odd_away": r.odd_away,
                    "collected_at": r.collected_at.isoformat() if r.collected_at else None,
                }
                for r in records
            ])
        finally:
            session.close()

    @app.route("/api/stats/daily")
    def api_daily_stats():
        """Daily statistics for charts."""
        session = SessionFactory()
        try:
            days = int(request.args.get("days", 7))
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            reports = (
                session.query(DailyReport)
                .filter(DailyReport.report_date >= start_date)
                .order_by(DailyReport.report_date, DailyReport.report_time)
                .all()
            )

            daily = {}
            for r in reports:
                if r.report_date not in daily:
                    daily[r.report_date] = {
                        "date": r.report_date,
                        "total_events": 0,
                        "alerts_above": 0,
                        "alerts_below": 0,
                        "reports_count": 0,
                    }
                daily[r.report_date]["total_events"] = max(
                    daily[r.report_date]["total_events"], r.total_events
                )
                daily[r.report_date]["alerts_above"] += r.alerts_above
                daily[r.report_date]["alerts_below"] += r.alerts_below
                daily[r.report_date]["reports_count"] += 1

            return jsonify(list(daily.values()))
        finally:
            session.close()

    # ========================================
    # WEBHOOK ENDPOINTS — Input Manual via API
    # ========================================

    @app.route("/api/webhook/manual", methods=["POST"])
    @require_api_key
    def webhook_manual_input():
        """
        Submit odds data manually via API.

        POST body (JSON):
        {
            "data": "Jogo: Time A vs Time B\nCampeonato: LaLiga\n...",
            "date": "2026-03-08"  (optional)
        }

        Or POST body (plain text):
        Raw odds data in template format.
        """
        if _system_instance is None:
            return jsonify({"error": "System not initialized"}), 503

        # Accept JSON or plain text
        if request.is_json:
            body = request.get_json()
            input_text = body.get("data", "")
            target_date = body.get("date", "")
        else:
            input_text = request.get_data(as_text=True)
            target_date = request.args.get("date", "")

        if not input_text.strip():
            return jsonify({"error": "No data provided"}), 400

        try:
            loop = asyncio.new_event_loop()
            report = loop.run_until_complete(
                _system_instance.run_manual_analysis(input_text, target_date)
            )
            loop.close()

            return jsonify({
                "status": "ok",
                "report": report,
                "message": "Relatório gerado e enviado ao Telegram.",
            })
        except Exception as e:
            logger.error(f"Webhook manual error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/webhook/scrape", methods=["POST"])
    @require_api_key
    def webhook_trigger_scrape():
        """
        Trigger a full scrape + analysis cycle via API.

        POST body (JSON, optional):
        {
            "date": "2026-03-08"
        }
        """
        if _system_instance is None:
            return jsonify({"error": "System not initialized"}), 503

        target_date = None
        if request.is_json:
            target_date = request.get_json().get("date")

        try:
            loop = asyncio.new_event_loop()
            report = loop.run_until_complete(
                _system_instance.run_analysis(target_date)
            )
            loop.close()

            return jsonify({
                "status": "ok",
                "report": report,
                "message": "Scraping e análise concluídos. Relatório enviado ao Telegram.",
            })
        except Exception as e:
            logger.error(f"Webhook scrape error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/webhook/test-telegram", methods=["POST"])
    @require_api_key
    def webhook_test_telegram():
        """Test Telegram connection."""
        if _system_instance is None:
            return jsonify({"error": "System not initialized"}), 503

        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                _system_instance.telegram.test_connection()
            )
            loop.close()

            return jsonify({
                "status": "ok" if result else "error",
                "connected": result,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ========================================
    # INPUT PAGE — Formulário web para colar dados
    # ========================================

    @app.route("/input")
    def input_page():
        return render_template("input.html")

    return app
