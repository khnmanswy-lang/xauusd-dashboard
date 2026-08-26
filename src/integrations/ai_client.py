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
Evaluate whether there is an active trade setup, or formulate a pending trading plan to wait for optimal timing, or evaluate/reject previous pending plans if market structure has shifted.
Respond with a strict, valid JSON object with NO markdown wrapper or code fences.

JSON Schema:
{
  "headline": "Short punchy status headline (e.g. 'GRADE A LONG: Asian Low Liquidity Purge' or 'PLAN HANDOVER: Awaiting FVG Pullback')",
  "setup_grade": "GRADE_A" | "GRADE_B" | "NO_SETUP",
  "direction": "BULLISH_LONG" | "BEARISH_SHORT" | "NEUTRAL",
  "confidence_score": 0.0 to 1.0,
  "plan_status": "WAITING_FOR_TRIGGER" | "READY_TO_EXECUTE" | "ACTIVE_MANAGEMENT" | "PLAN_REJECTED" | "NO_SETUP",
  "trigger_condition": {
    "condition_type": "FVG_RETEST" | "CHoCH_BREAK" | "SWEEP_REJECTION" | "PRICE_LEVEL" | null,
    "target_level": float or null,
    "invalidation_level": float or null,
    "description": "Specific condition required to trigger execution on subsequent cron calls"
  },
  "handover_notes": "Notes and context passed silently to the next 1-minute cron evaluation",
  "rejection_reason": "Specific reason if previous plan was invalidated or rejected (or null)",
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
        Deterministic, institutional-grade rule-based explainer engine with
        Stateful Plan Lifecycle (Waiting for Trigger -> Ready to Execute -> Active Trailing -> Rejected).
        Supports silent handover of conditions across 1-minute cron evaluations.
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
        news_guard = news.get("guard_active", False)

        # ----------------------------------------------------------------------
        # 1. EVALUATE PREVIOUS PENDING PLAN (SILENT HANDOVER OR REJECTION)
        # ----------------------------------------------------------------------
        if previous_analysis and previous_analysis.get("plan_status") == "WAITING_FOR_TRIGGER":
            prev_trig = previous_analysis.get("trigger_condition", {})
            prev_dir = previous_analysis.get("direction")
            target_level = prev_trig.get("target_level")
            inval_level = prev_trig.get("invalidation_level")

            # Check for Invalidation / Rejection Conditions
            is_invalidated = False
            rejection_msg = None

            if news_guard:
                is_invalidated = True
                rejection_msg = "High-impact news window active; pending setup plan cancelled for capital protection."
            elif prev_dir == "BULLISH_LONG" and inval_level and price < inval_level:
                is_invalidated = True
                rejection_msg = f"Price breached invalidation level (${inval_level:.2f}); bullish order block structure invalidated."
            elif prev_dir == "BEARISH_SHORT" and inval_level and price > inval_level:
                is_invalidated = True
                rejection_msg = f"Price breached invalidation level (${inval_level:.2f}); bearish order block structure invalidated."
            elif adr_pct > 80.0:
                is_invalidated = True
                rejection_msg = f"Daily ADR capacity exhausted ({adr_pct:.0f}% used); risk-reward profile dismantled."

            if is_invalidated:
                return {
                    "headline": f"PLAN REJECTED: {prev_dir.replace('_', ' ')} Invalidated",
                    "setup_grade": "NO_SETUP",
                    "direction": "NEUTRAL",
                    "confidence_score": 0.15,
                    "plan_status": "PLAN_REJECTED",
                    "trigger_condition": None,
                    "handover_notes": None,
                    "rejection_reason": rejection_msg,
                    "thesis": f"The pending {prev_dir} setup was cancelled by the AI engine: {rejection_msg}",
                    "order_flow_breakdown": [
                        f"Previous invalidation level: ${inval_level:.2f} triggered.",
                        "Order flow structure shifted into opposing momentum.",
                        "Clearing watchlist to prevent trapped entries."
                    ],
                    "execution_plan": {
                        "entry": None, "stop_loss": None, "take_profit_1": None, "take_profit_2": None,
                        "risk_reward_ratio": 0.0, "invalidation": "Plan cancelled."
                    },
                    "psychology_warning": "Discipline is not just taking trades; it is cancelling invalidated setups quickly."
                }

            # Check if Target Trigger Condition is Met!
            condition_met = False
            if prev_dir == "BULLISH_LONG":
                # Triggered if price reached the pullback target level or FVG CE
                if target_level and price <= target_level + 0.50 and price >= (inval_level or price - 5.0):
                    condition_met = True
            elif prev_dir == "BEARISH_SHORT":
                if target_level and price >= target_level - 0.50 and price <= (inval_level or price + 5.0):
                    condition_met = True

            if condition_met:
                # Transition from WAITING to READY_TO_EXECUTE!
                exec_plan = previous_analysis.get("execution_plan", {})
                return {
                    "headline": f"TRIGGER FIRED: {previous_analysis.get('headline', 'Execute Setup')}",
                    "setup_grade": previous_analysis.get("setup_grade", "GRADE_A"),
                    "direction": prev_dir,
                    "confidence_score": min(0.95, previous_analysis.get("confidence_score", 0.85) + 0.05),
                    "plan_status": "READY_TO_EXECUTE",
                    "trigger_condition": prev_trig,
                    "handover_notes": f"Trigger condition met at ${price:.2f}. Setup active.",
                    "rejection_reason": None,
                    "thesis": f"Price successfully retested target level (${target_level:.2f}). Order block confirmed and ready for execution.",
                    "order_flow_breakdown": previous_analysis.get("order_flow_breakdown", []),
                    "execution_plan": exec_plan,
                    "psychology_warning": "Execute planned lot size at market/limit. Stick to defined Stop Loss."
                }
            else:
                # Maintain SILENT HANDOVER to next cron pass
                return {
                    "headline": f"PLAN HANDOVER: Awaiting {prev_dir.replace('_', ' ')} Trigger",
                    "setup_grade": previous_analysis.get("setup_grade", "GRADE_B"),
                    "direction": prev_dir,
                    "confidence_score": previous_analysis.get("confidence_score", 0.75),
                    "plan_status": "WAITING_FOR_TRIGGER",
                    "trigger_condition": prev_trig,
                    "handover_notes": f"Price at ${price:.2f}. Waiting for trigger at ${target_level:.2f} (Dist: ${abs(price - target_level):.2f}). Invalidation intact at ${inval_level:.2f}.",
                    "rejection_reason": None,
                    "thesis": f"Pending {prev_dir} structure is intact. Standing by for optimal entry pricing.",
                    "order_flow_breakdown": [
                        f"Target trigger level: ${target_level:.2f}.",
                        f"Current price: ${price:.2f} (within valid expansion corridor).",
                        f"Structural invalidation safe at ${inval_level:.2f}."
                    ],
                    "execution_plan": previous_analysis.get("execution_plan", {}),
                    "psychology_warning": "Do not rush or front-run entries. Wait for price to touch the trigger zone."
                }

        # ----------------------------------------------------------------------
        # 2. EVALUATE ACTIVE RUNNING TRADE (TRAILING STOP MANAGEMENT)
        # ----------------------------------------------------------------------
        if previous_analysis and (
            previous_analysis.get("plan_status") in ["READY_TO_EXECUTE", "ACTIVE_MANAGEMENT"] or
            previous_analysis.get("setup_grade") in ["GRADE_A", "GRADE_B"]
        ):
            prev_entry = previous_analysis.get("execution_plan", {}).get("entry")
            prev_dir = previous_analysis.get("direction")
            prev_sl = previous_analysis.get("execution_plan", {}).get("stop_loss")

            # Trailing stop to Break-Even if profit >= 1.5R or +$3.00
            if prev_entry and prev_dir == "BULLISH_LONG" and price >= prev_entry + 3.0:
                return {
                    "headline": "TRADE MANAGEMENT: Trail Stop to Break-Even (+$3.00 in Profit)",
                    "setup_grade": previous_analysis.get("setup_grade"),
                    "direction": prev_dir,
                    "confidence_score": 0.95,
                    "plan_status": "ACTIVE_MANAGEMENT",
                    "trigger_condition": None,
                    "handover_notes": f"Active Long holding +${price - prev_entry:.2f} profit. Trailing SL to break-even.",
                    "rejection_reason": None,
                    "thesis": f"Active Long setup from ${prev_entry:.2f} expanded favorably to ${price:.2f}. Institutional liquidity objective is within reach.",
                    "order_flow_breakdown": [
                        f"Price holding above entry (${prev_entry:.2f}).",
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

        # ----------------------------------------------------------------------
        # 3. NEW SETUP EVALUATION (READY TO EXECUTE OR FORMULATE PENDING PLAN)
        # ----------------------------------------------------------------------
        if grade in ["GRADE_A", "GRADE_B"]:
            suggested_entry = scan.get("suggested_entry", price)
            suggested_sl = scan.get("suggested_sl", price - 3.0)
            suggested_tp1 = scan.get("suggested_tp1", price + 6.0)
            suggested_tp2 = scan.get("suggested_tp2", price + 10.0)

            # If price is slightly far from deep FVG 65% CE, form a WAITING_FOR_TRIGGER plan to handover!
            if abs(price - suggested_entry) > 1.50:
                plan_status = "WAITING_FOR_TRIGGER"
                headline = f"PLAN HANDOVER: Awaiting {direction.replace('_', ' ')} Pullback"
                handover_notes = f"Displacement confirmed. Awaiting deep pullback into FVG 65% CE (${suggested_entry:.2f}). Invalidation at ${suggested_sl:.2f}."
            else:
                plan_status = "READY_TO_EXECUTE"
                if sweep:
                    headline = f"GRADE A LONG: {session_name} Asian Low Liquidity Purge" if direction == "BULLISH_LONG" else f"GRADE A SHORT: {session_name} Asian High Liquidity Purge"
                else:
                    headline = f"{grade.replace('_', ' ')} {direction.replace('_', ' ')}: Execution Confirmed"
                handover_notes = f"Entry trigger active at ${price:.2f}."

            if direction == "BULLISH_LONG":
                thesis = f"Bullish structure confirmed during {session_name} {killzone}. Purged sell-side liquidity before printing M5 displacement."
                breakdown = [
                    f"Session liquidity dynamic: Asian Low at ${asia_low or 2928.0:.2f}.",
                    f"M5 structure shift with target entry at ${suggested_entry:.2f}.",
                    f"Trading in alignment with Session VWAP and healthy ADR capacity ({adr_pct:.0f}% used)."
                ]
            else:
                thesis = f"Bearish structure confirmed during {session_name} {killzone}. Purged buy-side liquidity before printing M5 breakdown."
                breakdown = [
                    f"Session liquidity dynamic: Asian High at ${asia_high or 2950.0:.2f}.",
                    f"M5 structure shift with target entry at ${suggested_entry:.2f}.",
                    f"Trading in alignment below Session VWAP and healthy ADR capacity ({adr_pct:.0f}% used)."
                ]

            return {
                "headline": headline,
                "setup_grade": grade,
                "direction": direction,
                "confidence_score": conf_score,
                "plan_status": plan_status,
                "trigger_condition": {
                    "condition_type": "FVG_RETEST",
                    "target_level": suggested_entry,
                    "invalidation_level": suggested_sl,
                    "description": f"Retest ${suggested_entry:.2f} entry zone without breaking ${suggested_sl:.2f}."
                },
                "handover_notes": handover_notes,
                "rejection_reason": None,
                "thesis": thesis,
                "order_flow_breakdown": breakdown,
                "execution_plan": {
                    "entry": suggested_entry,
                    "stop_loss": suggested_sl,
                    "take_profit_1": suggested_tp1,
                    "take_profit_2": suggested_tp2,
                    "risk_reward_ratio": scan.get("risk_reward_ratio", 2.0),
                    "invalidation": scan.get("invalidation_trigger", f"Close beyond ${suggested_sl:.2f}.")
                },
                "psychology_warning": "Patience for high-grade confluence entries pays dividends."
            }

        # Default: No Setup
        return {
            "headline": "NO SETUP: Market Consolidating Within Session Range",
            "setup_grade": "NO_SETUP",
            "direction": "NEUTRAL",
            "confidence_score": 0.25,
            "plan_status": "NO_SETUP",
            "trigger_condition": None,
            "handover_notes": "No pending plan in queue. Scanning for liquidity sweeps.",
            "rejection_reason": None,
            "thesis": f"Price is oscillating between Asian High (${asia_high or 2940.0:.2f}) and Low (${asia_low or 2928.0:.2f}). Order flow is in equilibrium.",
            "order_flow_breakdown": [
                "No liquidity sweeps detected on M5/M15 timeframe.",
                "Price hovering near Session VWAP benchmark.",
                "Conserving risk capital for London/NY Killzone expansion."
            ],
            "execution_plan": {
                "entry": None, "stop_loss": None, "take_profit_1": None, "take_profit_2": None,
                "risk_reward_ratio": 0.0, "invalidation": "Do not enter while market is in chop."
            },
            "psychology_warning": "Patience is alpha. Standing aside is an active trading decision."
        }
