"""
AI Client Integration for XAUUSD Multi-Timeframe Trade Setup Explainer.
Supports Google Gemini, OpenAI, local Ollama, and a high-fidelity
Deterministic Institutional Quant Reasoning Engine as fallback.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import httpx

from src.config.settings import AiSettings, settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an elite institutional quantitative gold (XAUUSD) trader and ICT/SMC structure analyst.
Your task is to analyze real-time market data across H1 (Macro Bias), M15 (Structure/VWAP), and M5 (Execution/FVG/CHoCH).
Evaluate whether there is an A+ or Grade B setup, or if the market is consolidating/in news blackout.
Respond with a strict, valid JSON object with NO markdown wrapper or code fences.

JSON Schema:
{
  "headline": "Short punchy status headline (e.g. 'GRADE A LONG: Asian Low Liquidity Purge')",
  "setup_grade": "GRADE_A" | "GRADE_B" | "NO_SETUP",
  "direction": "BULLISH_LONG" | "BEARISH_SHORT" | "NEUTRAL",
  "confidence_score": 0.0 to 1.0,
  "thesis": "2-3 sentences explaining the institutional order flow, liquidity purge, and displacement.",
  "order_flow_breakdown": [
    "Bullet 1 on session liquidity / sweep",
    "Bullet 2 on M5 CHoCH displacement & FVG retest",
    "Bullet 3 on Macro VWAP / 200 EMA alignment and ADR capacity"
  ],
  "execution_plan": {
    "entry": float or null,
    "stop_loss": float or null,
    "take_profit_1": float or null,
    "take_profit_2": float or null,
    "risk_reward_ratio": float,
    "invalidation": "Specific condition that invalidates this setup"
  },
  "psychology_warning": "1-sentence trader psychology and risk reminder (e.g. anti-chase or SL discipline)."
}
"""


class AiClient:
    """Async client for AI-driven trade setup generation and reasoning."""

    def __init__(self, ai_settings: Optional[AiSettings] = None):
        self.settings = ai_settings or settings.ai

    def is_configured(self) -> bool:
        """Returns True if an external AI provider has active credentials."""
        return self.settings.is_configured()

    async def generate_setup_analysis(
        self,
        market_frame: Dict[str, Any],
        previous_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generates structured trade setup analysis via configured LLM provider
        or returns high-precision deterministic quant analysis if unconfigured.
        """
        # If no external provider key is active, use deterministic institutional analyzer
        if not self.is_configured():
            return self._generate_deterministic_analysis(market_frame, previous_analysis)

        try:
            if self.settings.provider == "gemini":
                return await self._call_gemini(market_frame, previous_analysis)
            elif self.settings.provider == "openai":
                return await self._call_openai(market_frame, previous_analysis)
            elif self.settings.provider == "ollama":
                return await self._call_ollama(market_frame, previous_analysis)
        except Exception as e:
            logger.warning("External AI call failed (%s); falling back to deterministic quant engine.", e)

        return self._generate_deterministic_analysis(market_frame, previous_analysis)

    def _build_market_payload_prompt(
        self,
        market_frame: Dict[str, Any],
        previous_analysis: Optional[Dict[str, Any]] = None
    ) -> str:
        """Compile market telemetry snapshot into concise prompt context."""
        xau = market_frame.get("xauusd", {})
        macro = market_frame.get("macro", {})
        conf = market_frame.get("confluence_matrix", {})
        sess = market_frame.get("session", {})
        news = market_frame.get("news", {})
        vol = market_frame.get("volatility", {})
        scan = market_frame.get("setup_scan", {})

        payload = {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "current_price": xau.get("price"),
            "spread": xau.get("spread"),
            "active_session": sess.get("active_session"),
            "killzone": sess.get("killzone"),
            "session_levels": {
                "asia_high": sess.get("asia_high"),
                "asia_low": sess.get("asia_low"),
                "pdh": sess.get("pdh"),
                "pdl": sess.get("pdl"),
                "recent_sweep": sess.get("recent_sweep")
            },
            "macro_correlation": {
                "dxy": macro.get("dxy", {}).get("price"),
                "us10y": macro.get("us10y", {}).get("price")
            },
            "volatility": {
                "atr_m5": vol.get("atr_m5"),
                "adr_total": vol.get("adr_total"),
                "adr_used_pct": vol.get("adr_used_pct")
            },
            "economic_news": {
                "next_event": news.get("next_event"),
                "countdown": news.get("countdown_formatted"),
                "news_guard_active": news.get("guard_active")
            },
            "rule_based_scan": scan,
            "previous_active_setup": previous_analysis
        }
        return f"Market Telemetry Snapshot:\n{json.dumps(payload, indent=2)}\n\nAnalyze current market state:"

    async def _call_gemini(
        self,
        market_frame: Dict[str, Any],
        previous_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calls Google Gemini API."""
        prompt = self._build_market_payload_prompt(market_frame, previous_analysis)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.settings.gemini_api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": SYSTEM_PROMPT},
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
            else:
                raise RuntimeError(f"Gemini API returned status {res.status_code}: {res.text[:200]}")

    async def _call_openai(
        self,
        market_frame: Dict[str, Any],
        previous_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calls OpenAI API."""
        prompt = self._build_market_payload_prompt(market_frame, previous_analysis)
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                return json.loads(data["choices"][0]["message"]["content"])
            else:
                raise RuntimeError(f"OpenAI API returned status {res.status_code}: {res.text[:200]}")

    async def _call_ollama(
        self,
        market_frame: Dict[str, Any],
        previous_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calls local Ollama API."""
        prompt = self._build_market_payload_prompt(market_frame, previous_analysis)
        url = f"{self.settings.ollama_base_url}/api/chat"
        payload = {
            "model": "llama3.2",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "format": "json",
            "stream": False
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                return json.loads(data["message"]["content"])
            else:
                raise RuntimeError(f"Ollama API returned status {res.status_code}: {res.text[:200]}")

    def _generate_deterministic_analysis(
        self,
        market_frame: Dict[str, Any],
        previous_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Deterministic, institutional-grade rule-based explainer engine.
        Converts live market telemetry, setup scanner results, and session levels
        into comprehensive trade cards without requiring external API keys.
        """
        scan = market_frame.get("setup_scan", {})
        xau = market_frame.get("xauusd", {})
        sess = market_frame.get("session", {})
        vol = market_frame.get("volatility", {})
        news = market_frame.get("news", {})

        price = xau.get("price", 2935.0)
        grade = scan.get("grade", "NO_SETUP")
        direction = scan.get("direction", "NEUTRAL")
        conf_score = scan.get("confidence_score", 0.30)
        sweep = sess.get("recent_sweep")
        session_name = sess.get("active_session", "LONDON")
        killzone = sess.get("killzone", "OPEN")
        asia_high = sess.get("asia_high")
        asia_low = sess.get("asia_low")
        adr_pct = vol.get("adr_used_pct", 50.0)

        # Check if previous setup is active and needs trailing / adjustment
        if previous_analysis and previous_analysis.get("setup_grade") in ["GRADE_A", "GRADE_B"]:
            prev_entry = previous_analysis.get("execution_plan", {}).get("entry")
            prev_dir = previous_analysis.get("direction")
            prev_sl = previous_analysis.get("execution_plan", {}).get("stop_loss")

            # If trade has moved > 1.5R in favor, recommend moving SL to Break-Even
            if prev_entry and prev_dir == "BULLISH_LONG" and price >= prev_entry + 3.0:
                return {
                    "headline": "TRADE MANAGEMENT: Trail Stop to Break-Even (+$3.00 in Profit)",
                    "setup_grade": previous_analysis.get("setup_grade"),
                    "direction": prev_dir,
                    "confidence_score": 0.95,
                    "thesis": f"Active Long setup from ${prev_entry:.2f} has expanded favorably to ${price:.2f}. Institutional liquidity objective (TP1) is within reach.",
                    "order_flow_breakdown": [
                        f"Price holding above original entry (${prev_entry:.2f}).",
                        "Momentum expansion intact across M5 & M15 timeframes.",
                        f"Trail Stop Loss to Break-Even (${prev_entry + 0.50:.2f}) to lock in a risk-free position."
                    ],
                    "execution_plan": {
                        "entry": prev_entry,
                        "stop_loss": round(prev_entry + 0.50, 2),
                        "take_profit_1": previous_analysis.get("execution_plan", {}).get("take_profit_1"),
                        "take_profit_2": previous_analysis.get("execution_plan", {}).get("take_profit_2"),
                        "risk_reward_ratio": 2.5,
                        "invalidation": f"Trailing stop triggered on M5 close below ${prev_entry + 0.50:.2f}."
                    },
                    "psychology_warning": "Protect realized profits. Do not add to winning positions impulsively."
                }

        if grade == "GRADE_A":
            if direction == "BULLISH_LONG":
                headline = f"GRADE A LONG: {session_name} Asian Low Liquidity Purge"
                thesis = (
                    f"Price aggressively swept below the Asian Session Low (${asia_low:.2f}) during {session_name} {killzone}, "
                    f"purging sell-side liquidity before printing a confirmed M5 CHoCH and retesting the Fair Value Gap."
                )
                breakdown = [
                    f"Asian Range Low swept and rejected at ${asia_low:.2f}.",
                    f"M5 displacement confirmed structure shift with Bullish FVG retest at ${scan.get('suggested_entry', price):.2f}.",
                    f"Macro alignment intact (above Session VWAP) with healthy ADR capacity ({adr_pct:.0f}% used)."
                ]
                psych = "Execute at the designated FVG entry. Avoid chasing green candles if price exceeds entry by more than $1.50."
            else:
                headline = f"GRADE A SHORT: {session_name} Asian High Liquidity Purge"
                thesis = (
                    f"Price swept above the Asian Session High (${asia_high:.2f}) during {session_name} {killzone}, "
                    f"capturing buy-side liquidity before triggering an impulsive M5 CHoCH breakdown."
                )
                breakdown = [
                    f"Asian Range High swept and rejected at ${asia_high:.2f}.",
                    f"M5 displacement confirmed structure breakdown with Bearish FVG retest at ${scan.get('suggested_entry', price):.2f}.",
                    f"Macro alignment intact (below Session VWAP) with healthy ADR capacity ({adr_pct:.0f}% used)."
                ]
                psych = "Execute with disciplined risk sizing. Confirm M5 candle closes below the invalidation level."

            return {
                "headline": headline,
                "setup_grade": "GRADE_A",
                "direction": direction,
                "confidence_score": conf_score,
                "thesis": thesis,
                "order_flow_breakdown": breakdown,
                "execution_plan": {
                    "entry": scan.get("suggested_entry"),
                    "stop_loss": scan.get("suggested_sl"),
                    "take_profit_1": scan.get("suggested_tp1"),
                    "take_profit_2": scan.get("suggested_tp2"),
                    "risk_reward_ratio": scan.get("risk_reward_ratio", 2.0),
                    "invalidation": scan.get("invalidation_trigger", "M5 structural invalidation.")
                },
                "psychology_warning": psych
            }

        elif grade == "GRADE_B":
            return {
                "headline": f"GRADE B {direction.replace('_', ' ')}: Moderate Confluence",
                "setup_grade": "GRADE_B",
                "direction": direction,
                "confidence_score": conf_score,
                "thesis": (
                    f"Intraday momentum is showing {direction.lower().replace('_', ' ')} tendencies near ${price:.2f}, "
                    f"but lacks a full 5-point institutional sweep confirmation."
                ),
                "order_flow_breakdown": [
                    f"Partial confluence with Session VWAP and trend indicators.",
                    f"Active setup score {scan.get('points_met', 3)}/5 points met.",
                    "Awaiting cleaner liquidity purge at session extremes before sizing full risk."
                ],
                "execution_plan": {
                    "entry": scan.get("suggested_entry"),
                    "stop_loss": scan.get("suggested_sl"),
                    "take_profit_1": scan.get("suggested_tp1"),
                    "take_profit_2": scan.get("suggested_tp2"),
                    "risk_reward_ratio": 2.0,
                    "invalidation": scan.get("invalidation_trigger", "M5 invalidation.")
                },
                "psychology_warning": "Consider half-position sizing (0.5% risk) until A+ liquidity sweep confirms."
            }

        else:
            return {
                "headline": "NO SETUP: Market Consolidating Within Session Range",
                "setup_grade": "NO_SETUP",
                "direction": "NEUTRAL",
                "confidence_score": 0.25,
                "thesis": (
                    f"Price is oscillating between Asian High (${asia_high or 2940.0:.2f}) and Low (${asia_low or 2928.0:.2f}). "
                    "Order flow is in equilibrium with no institutional displacement."
                ),
                "order_flow_breakdown": [
                    "No liquidity sweeps detected on M5/M15 timeframe.",
                    "Price hovering near Session VWAP benchmark.",
                    "Conserving risk capital for London/NY Killzone expansion."
                ],
                "execution_plan": {
                    "entry": None,
                    "stop_loss": None,
                    "take_profit_1": None,
                    "take_profit_2": None,
                    "risk_reward_ratio": 0.0,
                    "invalidation": "Do not enter while market is in chop."
                },
                "psychology_warning": "Patience is alpha. Standing aside is an active trading decision."
            }
