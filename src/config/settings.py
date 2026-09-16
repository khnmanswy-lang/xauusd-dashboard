"""
Application Configuration and Settings.
Loads environment variables and sets defaults for market feeds, session schedules, and risk parameters.
Pure deterministic quantitative configuration with zero external broker or AI dependencies.
"""
from dataclasses import dataclass, field
import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


@dataclass
class MarketDataSettings:
    """Settings for real-time market data streaming."""
    symbol: str = "XAUUSD"
    # Public Binance PAXGUSDT stream is used as a 24/7 real-time Gold spot proxy (zero API key needed)
    binance_ws_url: str = os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443/ws/paxgusdt@kline_1m")
    binance_ticker_ws_url: str = os.getenv("BINANCE_TICKER_WS_URL", "wss://stream.binance.com:9443/ws/paxgusdt@ticker")
    binance_rest_klines_url: str = os.getenv("BINANCE_REST_KLINES_URL", "https://api.binance.com/api/v3/klines")
    
    # Fallback / Simulated tick interval (seconds) if external feed is disconnected
    simulation_enabled: bool = os.getenv("ENABLE_SIMULATION_FALLBACK", "true").lower() == "true"
    reconnect_delay_seconds: int = 3
    max_history_bars: int = 2880


@dataclass
class MacroSettings:
    """Settings for macro correlation feeds (DXY, US10Y)."""
    poll_interval_seconds: int = int(os.getenv("MACRO_POLL_INTERVAL", "60"))
    dxy_ticker: str = "DX-Y.NYB"
    us10y_ticker: str = "^TNX"


@dataclass
class SessionSettings:
    """Session trading hours in UTC (Hour, Minute)."""
    asia_start: int = 0      # 00:00 UTC
    asia_end: int = 8        # 08:00 UTC
    london_start: int = 7    # 07:00 UTC
    london_end: int = 16     # 16:00 UTC
    ny_start: int = 12       # 12:00 UTC
    ny_end: int = 21         # 21:00 UTC


@dataclass
class RiskSettings:
    """Default risk and lot sizing calculation parameters."""
    default_balance: float = float(os.getenv("DEFAULT_BALANCE", "10000.0"))
    default_risk_pct: float = float(os.getenv("DEFAULT_RISK_PCT", "1.0"))
    atr_sl_multiplier: float = 1.5
    min_lot_size: float = 0.01
    contract_size_oz: float = 100.0  # Standard gold contract: 100 troy oz


@dataclass
class AlgoSettings:
    """Settings for Pure Deterministic Algorithmic Setup Scanner & Reasoning Engine."""
    scanner_interval_seconds: int = int(os.getenv("SCANNER_INTERVAL_SECONDS", "60"))
    min_confidence_score: float = float(os.getenv("MIN_CONFIDENCE_SCORE", "0.85"))
    max_spread_pips: float = float(os.getenv("MAX_SPREAD_PIPS", "30.0"))

    def is_configured(self) -> bool:
        """Always True for deterministic quantitative algorithms."""
        return True


@dataclass
class AppSettings:
    """Global Dashboard Settings."""
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    reload: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    market: MarketDataSettings = field(default_factory=MarketDataSettings)
    algo: AlgoSettings = field(default_factory=AlgoSettings)
    macro: MacroSettings = field(default_factory=MacroSettings)
    session: SessionSettings = field(default_factory=SessionSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)


settings = AppSettings()
