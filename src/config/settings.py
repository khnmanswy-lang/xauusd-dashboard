"""
Application Configuration and Settings.
Loads environment variables and sets defaults for market feeds, session schedules, and risk parameters.
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
    # Public Binance PAXGUSDT stream is used as a 24/7 real-time Gold spot proxy
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
class OandaSettings:
    """Settings for OANDA v20 REST & Streaming API."""
    api_key: str = os.getenv("OANDA_API_KEY", "")
    account_id: str = os.getenv("OANDA_ACCOUNT_ID", "")
    environment: str = os.getenv("OANDA_ENV", "practice").lower()
    symbol: str = os.getenv("OANDA_SYMBOL", "XAU_USD")
    reconnect_delay_seconds: int = 3

    @property
    def rest_base_url(self) -> str:
        if self.environment == "live":
            return "https://api-fxtrade.oanda.com/v3"
        return "https://api-fxpractice.oanda.com/v3"

    @property
    def stream_base_url(self) -> str:
        if self.environment == "live":
            return "https://stream-fxtrade.oanda.com/v3"
        return "https://stream-fxpractice.oanda.com/v3"

    def is_configured(self) -> bool:
        """Returns True if valid OANDA credentials are present."""
        if not self.api_key or not self.account_id:
            return False
        if "your_oanda" in self.api_key.lower() or "xxxx" in self.account_id.lower():
            return False
        return True


@dataclass
class AiSettings:
    """Settings for AI Setup Scanner & Reasoning Engine."""
    provider: str = os.getenv("AI_PROVIDER", "gemini").lower()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    scanner_interval_seconds: int = int(os.getenv("SCANNER_INTERVAL_SECONDS", "60"))
    min_confidence_score: float = float(os.getenv("MIN_CONFIDENCE_SCORE", "0.85"))
    max_spread_pips: float = float(os.getenv("MAX_SPREAD_PIPS", "30.0"))

    def is_configured(self) -> bool:
        """Returns True if configured for active AI generation."""
        if self.provider == "gemini":
            return bool(self.gemini_api_key and "your_gemini" not in self.gemini_api_key.lower())
        elif self.provider == "openai":
            return bool(self.openai_api_key and "your_openai" not in self.openai_api_key.lower())
        elif self.provider == "ollama":
            return bool(self.ollama_base_url)
        return False


@dataclass
class AppSettings:
    """Global Dashboard Settings."""
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    reload: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    market: MarketDataSettings = field(default_factory=MarketDataSettings)
    oanda: OandaSettings = field(default_factory=OandaSettings)
    ai: AiSettings = field(default_factory=AiSettings)
    macro: MacroSettings = field(default_factory=MacroSettings)
    session: SessionSettings = field(default_factory=SessionSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)


settings = AppSettings()
