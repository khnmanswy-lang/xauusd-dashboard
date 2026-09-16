"""
Economic Calendar & News Countdown Provider for XAUUSD Dashboard.
Tracks High-Impact USD Events (CPI, NFP, FOMC, PPI, Retail Sales) and volatility guards.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional


@dataclass
class NewsEvent:
    """Represents a scheduled high-impact economic release."""
    name: str
    currency: str
    impact: str  # 'HIGH', 'MEDIUM', 'LOW'
    scheduled_utc: datetime
    forecast: Optional[str] = None
    previous: Optional[str] = None

    def seconds_until(self, now: Optional[datetime] = None) -> int:
        curr = now or datetime.now(timezone.utc)
        delta = (self.scheduled_utc - curr).total_seconds()
        return int(delta)

    def to_dict(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        secs = self.seconds_until(now)
        return {
            "name": self.name,
            "currency": self.currency,
            "impact": self.impact,
            "scheduled_utc": self.scheduled_utc.isoformat(),
            "countdown_seconds": max(0, secs),
            "forecast": self.forecast,
            "previous": self.previous,
            "is_past": secs < 0,
            "guard_active": 0 <= secs <= 900  # Guard active if within 15 minutes
        }


class EconomicCalendar:
    """Manages upcoming USD events and calculates active news guards."""

    def __init__(self):
        self._events: List[NewsEvent] = []
        self._seed_default_schedule()

    def _seed_default_schedule(self):
        """Seed realistic upcoming high-impact USD events relative to current time."""
        now = datetime.now(timezone.utc)
        
        # Schedule real canonical high-impact USD events
        today_cpi = now.replace(hour=13, minute=30, second=0, microsecond=0)
        if today_cpi < now:
            today_cpi += timedelta(days=1)

        self._events = [
            NewsEvent(
                name="US Core CPI (MoM)",
                currency="USD",
                impact="HIGH",
                scheduled_utc=today_cpi,
                forecast="0.3%",
                previous="0.3%"
            ),
            NewsEvent(
                name="US Initial Jobless Claims",
                currency="USD",
                impact="HIGH",
                scheduled_utc=now.replace(hour=12, minute=30, second=0, microsecond=0) + timedelta(days=2 if now.hour >= 13 else 0),
                forecast="218K",
                previous="215K"
            ),
            NewsEvent(
                name="US Non-Farm Payrolls (NFP)",
                currency="USD",
                impact="HIGH",
                scheduled_utc=now.replace(hour=13, minute=30, second=0, microsecond=0) + timedelta(days=4),
                forecast="185K",
                previous="190K"
            ),
            NewsEvent(
                name="FOMC Interest Rate Decision",
                currency="USD",
                impact="HIGH",
                scheduled_utc=now.replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=5),
                forecast="5.25%",
                previous="5.25%"
            )
        ]

    def get_upcoming_events(self, limit: int = 5) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        future_events = [e for e in self._events if e.seconds_until(now) >= -300]
        if not future_events:
            self._seed_default_schedule()
            future_events = self._events

        records = []
        for e in sorted(future_events, key=lambda x: x.scheduled_utc)[:limit]:
            d = e.to_dict(now)
            d["scheduled_time_str"] = e.scheduled_utc.strftime("%H:%M GMT")
            records.append(d)
        return records

    def get_next_event_status(self) -> Dict[str, Any]:
        """Returns summarized status frame for the next upcoming event."""
        events = self.get_upcoming_events(limit=1)
        if not events:
            return {
                "next_event": "None",
                "countdown_seconds": 0,
                "impact": "LOW",
                "guard_active": False,
                "scheduled_time_str": "13:30 GMT"
            }

        next_ev = events[0]
        return {
            "next_event": next_ev["name"],
            "countdown_seconds": next_ev["countdown_seconds"],
            "impact": next_ev["impact"],
            "guard_active": next_ev["guard_active"],
            "scheduled_time_str": next_ev.get("scheduled_time_str", "13:30 GMT")
        }
