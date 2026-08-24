"""
AI Setup Analyzer & Cron Job Coordinator.
Periodically scans market structure, evaluates active trade setups,
and triggers AI-generated trade plans and risk commentary.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any, Set

from src.integrations.ai_client import AiClient
from src.integrations.market_data import MarketDataEngine

logger = logging.getLogger(__name__)


class AiSetupAnalyzer:
    """Coordinates periodic cron evaluations and live AI analysis generation."""

    def __init__(
        self,
        market_engine: MarketDataEngine,
        ai_client: Optional[AiClient] = None
    ):
        self.market_engine = market_engine
        self.ai_client = ai_client or AiClient()
        self._latest_analysis: Dict[str, Any] = {}
        self._listeners: Set[Callable[[Dict[str, Any]], Any]] = set()
        self._lock = asyncio.Lock()

    def get_latest_analysis(self) -> Dict[str, Any]:
        """Returns the most recent AI analysis card."""
        if not self._latest_analysis:
            # Generate initial fallback if none exists yet
            frame = self.market_engine.get_state_frame()
            self._latest_analysis = self.ai_client._generate_deterministic_analysis(frame, None)
            self._latest_analysis["timestamp"] = int(datetime.now(timezone.utc).timestamp())
        return self._latest_analysis

    def add_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        """Subscribe to new AI analysis updates."""
        self._listeners.add(callback)

    def remove_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        """Unsubscribe from AI analysis updates."""
        self._listeners.discard(callback)

    async def _notify_listeners(self, analysis: Dict[str, Any]):
        """Broadcast updated analysis to all subscribers (e.g. WebSockets)."""
        payload = {
            "type": "AI_ANALYSIS_UPDATE",
            "data": analysis,
            "timestamp": int(datetime.now(timezone.utc).timestamp())
        }
        for listener in list(self._listeners):
            try:
                res = listener(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.debug("Error notifying AI analysis listener: %s", e)

    async def evaluate_market(self) -> Dict[str, Any]:
        """
        Executes a full market evaluation pass.
        Called by the 60s / 1-minute cron job or on-demand via REST endpoint.
        """
        async with self._lock:
            try:
                frame = self.market_engine.get_state_frame()
                analysis = await self.ai_client.generate_setup_analysis(
                    market_frame=frame,
                    previous_analysis=self._latest_analysis if self._latest_analysis else None
                )
                analysis["timestamp"] = int(datetime.now(timezone.utc).timestamp())
                analysis["last_evaluated_utc"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                self._latest_analysis = analysis
                logger.info(
                    "AI Market Evaluation pass completed: [%s] %s (Conf: %.0f%%)",
                    analysis.get("setup_grade", "NO_SETUP"),
                    analysis.get("headline", ""),
                    float(analysis.get("confidence_score", 0.0)) * 100
                )

                await self._notify_listeners(analysis)
                return analysis
            except Exception as e:
                logger.error("Error during AI market evaluation pass: %s", e)
                return self.get_latest_analysis()
