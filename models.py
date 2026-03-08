"""Database models for the ROP Odds Mapping System."""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, DateTime, Text, Boolean,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class ScrapeSession(Base):
    """A single scraping session (e.g., 09:00 run on 2026-03-08)."""
    __tablename__ = "scrape_sessions"

    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")  # running, completed, failed
    total_events = Column(Integer, default=0)
    total_alerts = Column(Integer, default=0)

    odds = relationship("OddsRecord", back_populates="session")
    alerts = relationship("Alert", back_populates="session")


class OddsRecord(Base):
    """A single odds record: one site's odds for one event + market."""
    __tablename__ = "odds_records"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("scrape_sessions.id"), nullable=False)
    collected_at = Column(DateTime, default=datetime.utcnow)

    # Event info
    championship = Column(String(100))
    home_team = Column(String(100))
    away_team = Column(String(100))
    match_time = Column(String(20))  # HH:MM BRT
    match_date = Column(String(10))  # YYYY-MM-DD

    # Site info
    site_name = Column(String(50))
    site_type = Column(String(20))  # main or competitor

    # Market: 1x2
    odd_home = Column(Float, nullable=True)
    odd_draw = Column(Float, nullable=True)
    odd_away = Column(Float, nullable=True)

    # Market: BTTS
    odd_btts_yes = Column(Float, nullable=True)
    odd_btts_no = Column(Float, nullable=True)

    # Market: Over/Under 2.5
    odd_over_25 = Column(Float, nullable=True)
    odd_under_25 = Column(Float, nullable=True)

    # Market: Over/Under 1.5
    odd_over_15 = Column(Float, nullable=True)
    odd_under_15 = Column(Float, nullable=True)

    # Market: Over/Under 3.5
    odd_over_35 = Column(Float, nullable=True)
    odd_under_35 = Column(Float, nullable=True)

    # Market: Double Chance
    odd_dc_1x = Column(Float, nullable=True)
    odd_dc_12 = Column(Float, nullable=True)
    odd_dc_x2 = Column(Float, nullable=True)

    session = relationship("ScrapeSession", back_populates="odds")

    __table_args__ = (
        Index("idx_session_event", "session_id", "home_team", "away_team", "site_name"),
    )


class Alert(Base):
    """An alert generated when ROP odds deviate from market average."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("scrape_sessions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Event
    championship = Column(String(100))
    home_team = Column(String(100))
    away_team = Column(String(100))
    match_time = Column(String(20))

    # Alert details
    market = Column(String(50))  # e.g., "1X2 - Casa", "BTTS - Sim"
    rop_odd = Column(Float)
    market_avg = Column(Float)
    deviation_pct = Column(Float)  # positive = above avg, negative = below
    alert_type = Column(String(10))  # "above" or "below"
    severity = Column(String(10))  # "high", "medium"

    # Status
    sent_telegram = Column(Boolean, default=False)

    session = relationship("ScrapeSession", back_populates="alerts")


class DailyReport(Base):
    """Stored daily reports for the dashboard."""
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("scrape_sessions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    report_date = Column(String(10))  # YYYY-MM-DD
    report_time = Column(String(5))   # HH:MM
    report_text = Column(Text)
    total_events = Column(Integer, default=0)
    alerts_above = Column(Integer, default=0)
    alerts_below = Column(Integer, default=0)


def init_db(database_url="sqlite:///data/ropodds.db"):
    """Initialize the database and return engine + session."""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
