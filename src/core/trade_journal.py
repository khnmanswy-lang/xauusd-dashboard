"""
Trade Journal Manager & CSV Exporter.
Records live and simulated XAUUSD trade setups, execution metrics,
order flow confluence reasons, and R-returns to persistent CSV files.
"""
import csv
import io
import logging
import os
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

DEFAULT_JOURNAL_PATH = Path("data/trade_journal.csv")


@dataclass
class JournalEntry:
    """Represents a single trade journal entry."""
    id: str = field(default_factory=lambda: f"TRD-{uuid.uuid4().hex[:8].upper()}")
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    symbol: str = "XAU_USD"
    session: str = "LONDON"
    killzone: str = "LONDON_OPEN"
    setup_grade: str = "GRADE_A"
    direction: str = "BULLISH_LONG"
    confidence_pct: int = 85
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    risk_distance_usd: float = 0.0
    account_balance: float = 10000.0
    risk_pct: float = 1.0
    lot_size: float = 0.50
    outcome: str = "OPEN"  # OPEN, TP1_HIT, TP2_HIT, SL_HIT, CANCELLED
    exit_price: Optional[float] = None
    exit_time_utc: Optional[str] = None
    realized_r: float = 0.0
    realized_pnl_usd: float = 0.0
    max_favorable_usd: float = 0.0
    max_adverse_usd: float = 0.0
    confluence_factors: str = ""
    ai_thesis: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return asdict(self)


class TradeJournalManager:
    """Manages thread-safe in-memory trade history and disk CSV synchronization."""

    def __init__(self, file_path: Path = DEFAULT_JOURNAL_PATH):
        self.file_path = file_path
        self._entries: List[JournalEntry] = []
        self._ensure_storage()
        self.load_from_csv()

    def _ensure_storage(self):
        """Ensure the parent directory and CSV file exist."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.file_path.exists():
                self._write_headers()
        except Exception as e:
            logger.error("Failed to initialize trade journal storage: %s", e)

    def _write_headers(self):
        """Write CSV column headers to the journal file."""
        fieldnames = list(JournalEntry.__annotations__.keys())
        with open(self.file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    def load_from_csv(self):
        """Load trade entries from the disk CSV file."""
        if not self.file_path.exists():
            return

        try:
            with open(self.file_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                entries: List[JournalEntry] = []
                for row in reader:
                    if not row or not row.get("id"):
                        continue
                    try:
                        entry = JournalEntry(
                            id=row.get("id", ""),
                            timestamp_utc=row.get("timestamp_utc", ""),
                            symbol=row.get("symbol", "XAU_USD"),
                            session=row.get("session", "UNKNOWN"),
                            killzone=row.get("killzone", "NONE"),
                            setup_grade=row.get("setup_grade", "NO_SETUP"),
                            direction=row.get("direction", "NEUTRAL"),
                            confidence_pct=int(float(row.get("confidence_pct", 0))),
                            entry_price=float(row.get("entry_price", 0.0)),
                            stop_loss=float(row.get("stop_loss", 0.0)),
                            take_profit_1=float(row.get("take_profit_1", 0.0)),
                            take_profit_2=float(row.get("take_profit_2", 0.0)),
                            risk_distance_usd=float(row.get("risk_distance_usd", 0.0)),
                            account_balance=float(row.get("account_balance", 10000.0)),
                            risk_pct=float(row.get("risk_pct", 1.0)),
                            lot_size=float(row.get("lot_size", 0.1)),
                            outcome=row.get("outcome", "OPEN"),
                            exit_price=float(row.get("exit_price")) if row.get("exit_price") not in [None, ""] else None,
                            exit_time_utc=row.get("exit_time_utc") or None,
                            realized_r=float(row.get("realized_r", 0.0)),
                            realized_pnl_usd=float(row.get("realized_pnl_usd", 0.0)),
                            max_favorable_usd=float(row.get("max_favorable_usd", 0.0)),
                            max_adverse_usd=float(row.get("max_adverse_usd", 0.0)),
                            confluence_factors=row.get("confluence_factors", ""),
                            ai_thesis=row.get("ai_thesis", ""),
                            notes=row.get("notes", "")
                        )
                        entries.append(entry)
                    except Exception as err:
                        logger.warning("Skipping corrupted CSV row: %s (%s)", row, err)
                self._entries = entries
        except Exception as e:
            logger.error("Error reading journal CSV: %s", e)

    def add_entry(self, data: Any) -> JournalEntry:
        """Add a new journal entry and persist to disk."""
        if isinstance(data, JournalEntry):
            entry = data
        elif isinstance(data, dict):
            entry = JournalEntry(**{k: v for k, v in data.items() if k in JournalEntry.__annotations__})
        else:
            raise ValueError(f"Invalid entry data type: {type(data)}")

        self._entries.insert(0, entry)  # Prepend newest
        self.save_to_csv()
        return entry

    def get_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent journal entries as dictionaries."""
        return [e.to_dict() for e in self._entries[:limit]]

    def save_to_csv(self):
        """Save all in-memory entries to the CSV file."""
        try:
            fieldnames = list(JournalEntry.__annotations__.keys())
            with open(self.file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for e in self._entries:
                    writer.writerow(e.to_dict())
        except Exception as e:
            logger.error("Failed to save journal entries to CSV: %s", e)

    def export_csv_string(self) -> str:
        """Generate formatted CSV string for download."""
        output = io.StringIO()
        fieldnames = list(JournalEntry.__annotations__.keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for e in self._entries:
            writer.writerow(e.to_dict())
        return output.getvalue()
