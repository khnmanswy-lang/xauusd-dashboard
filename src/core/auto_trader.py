"""
Auto-Execution Sentry & OANDA Practice Trader.
Enforces idempotent 60-second cron evaluations, strategy time-gating,
duplicate position guards, automated bracket order dispatching,
break-even trailing stop updates, and persistent trade journal recording.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from src.core.ai_analyzer import AiSetupAnalyzer
from src.core.risk_calculator import calculate_lot_size
from src.core.trade_journal import TradeJournalManager, JournalEntry
from src.integrations.market_data import MarketDataEngine
from src.integrations.oanda_client import OandaClient

logger = logging.getLogger(__name__)

# Valid high-volume institutional killzones in UTC hours
ALLOWED_KILLZONES = [
    (0, 0, 3, 0),    # Asian Open: 00:00 - 03:00 UTC
    (7, 30, 11, 30), # London Open: 07:30 - 11:30 UTC
    (12, 0, 14, 30)  # NY Open: 12:00 - 14:30 UTC
]


class AutoTrader:
    """Coordinates automated, idempotent execution to OANDA Practice Account."""

    def __init__(
        self,
        market_engine: MarketDataEngine,
        ai_analyzer: AiSetupAnalyzer,
        oanda_client: OandaClient,
        trade_journal: TradeJournalManager,
        enabled: bool = True,
        risk_per_trade_pct: float = 1.0,
        cooldown_seconds: int = 3600
    ):
        self.market_engine = market_engine
        self.ai_analyzer = ai_analyzer
        self.oanda_client = oanda_client
        self.trade_journal = trade_journal
        self.enabled = enabled and oanda_client.is_configured()
        self.risk_per_trade_pct = risk_per_trade_pct
        self.cooldown_seconds = cooldown_seconds
        self.last_trade_time: float = 0.0
        self._lock = asyncio.Lock()

    def is_in_killzone(self, dt: datetime) -> bool:
        """
        Check if current time is within active market trading session hours (00:00 - 22:00 UTC).
        """
        # Active gold trading hours across Asia, London, and NY sessions
        return 0 <= dt.hour < 22

    def toggle(self, state: Optional[bool] = None) -> bool:
        """Toggle or set auto-trader active state."""
        if state is not None:
            self.enabled = state
        else:
            self.enabled = not self.enabled
        logger.info("AutoTrader state changed: ENABLED = %s", self.enabled)
        return self.enabled

    async def evaluate_and_trade(self) -> Dict[str, Any]:
        """
        Main Cron Execution Pass: Evaluates market, manages active trades,
        or triggers new orders into OANDA practice account.
        """
        if not self.enabled:
            return {"status": "DISABLED", "message": "AutoTrader is disabled"}

        async with self._lock:
            now_dt = datetime.now(timezone.utc)
            now_ts = now_dt.timestamp()
            frame = self.market_engine.get_state_frame()
            price = frame.get("xauusd", {}).get("price", 2935.0)

            # ------------------------------------------------------------------
            # 1. IDEMPOTENCY: Check for Existing Open Position on OANDA
            # ------------------------------------------------------------------
            open_trades = await self.oanda_client.get_open_trades()
            if open_trades:
                trade = open_trades[0]
                trade_id = trade.get("id")
                entry_p = float(trade.get("price", price))
                units = float(trade.get("currentUnits", 0))
                direction = "BULLISH_LONG" if units > 0 else "BEARISH_SHORT"
                current_sl = float(trade.get("stopLossOrder", {}).get("price", 0.0)) if trade.get("stopLossOrder") else None

                # Check if eligible for Trailing Stop to Break-Even (+$3.00 profit)
                if direction == "BULLISH_LONG" and price >= entry_p + 3.0:
                    be_sl = round(entry_p + 0.50, 2)
                    if current_sl is None or current_sl < be_sl:
                        updated = await self.oanda_client.update_trade_stop_loss(trade_id, be_sl)
                        if updated:
                            logger.info("Trailed Stop Loss to Break-Even ($%.2f) on Trade #%s", be_sl, trade_id)
                            return {
                                "status": "TRAILING_UPDATED",
                                "trade_id": trade_id,
                                "new_stop_loss": be_sl,
                                "profit_usd": round(price - entry_p, 2)
                            }

                elif direction == "BEARISH_SHORT" and price <= entry_p - 3.0:
                    be_sl = round(entry_p - 0.50, 2)
                    if current_sl is None or current_sl > be_sl:
                        updated = await self.oanda_client.update_trade_stop_loss(trade_id, be_sl)
                        if updated:
                            logger.info("Trailed Stop Loss to Break-Even ($%.2f) on Trade #%s", be_sl, trade_id)
                            return {
                                "status": "TRAILING_UPDATED",
                                "trade_id": trade_id,
                                "new_stop_loss": be_sl,
                                "profit_usd": round(entry_p - price, 2)
                            }

                logger.info("[AutoTrader] Open position active on Trade #%s (%s units @ $%.2f). Skipping new entry.", trade_id, units, entry_p)
                return {
                    "status": "POSITION_OPEN",
                    "trade_id": trade_id,
                    "direction": direction,
                    "units": units,
                    "entry_price": entry_p,
                    "current_price": price
                }

            # ------------------------------------------------------------------
            # 2. STRATEGY CONSTRAINTS & FILTERS
            # ------------------------------------------------------------------
            # A. Cooldown Check (15 Minutes after previous filled trade)
            if now_ts - self.last_trade_time < self.cooldown_seconds:
                remaining_sec = int(self.cooldown_seconds - (now_ts - self.last_trade_time))
                logger.info("[AutoTrader] In cooldown (%dm remaining). Standing by.", round(remaining_sec / 60))
                return {
                    "status": "COOLDOWN",
                    "cooldown_remaining_min": round(remaining_sec / 60, 1),
                    "message": f"Cooldown active ({round(remaining_sec / 60, 1)}m remaining)"
                }

            # B. Session Hours Check
            if not self.is_in_killzone(now_dt):
                logger.info("[AutoTrader] Market session closed (UTC hour: %d).", now_dt.hour)
                return {
                    "status": "OUTSIDE_KILLZONE",
                    "current_utc": now_dt.strftime("%H:%M UTC"),
                    "message": "Standing aside outside active market session hours"
                }

            # C. ADR Exhaustion & News Check
            vol = frame.get("volatility", {})
            adr_used = vol.get("adr_used_pct", 50.0)
            if adr_used > 80.0:
                logger.info("[AutoTrader] ADR capacity exhausted (%.1f%% used).", adr_used)
                return {
                    "status": "ADR_EXHAUSTED",
                    "adr_used_pct": adr_used,
                    "message": f"ADR capacity exhausted ({adr_used:.0f}% used)"
                }

            news = frame.get("news", {})
            if news.get("guard_active", False):
                logger.info("[AutoTrader] High impact news blackout guard active.")
                return {
                    "status": "NEWS_BLACKOUT",
                    "message": "High-impact news blackout window active"
                }

            # ------------------------------------------------------------------
            # 3. SETUP & PLAN EVALUATION
            # ------------------------------------------------------------------
            analysis = self.ai_analyzer.get_latest_analysis()
            plan_status = analysis.get("plan_status", "NO_SETUP")
            grade = analysis.get("setup_grade", "NO_SETUP")
            direction = analysis.get("direction", "NEUTRAL")
            exec_plan = analysis.get("execution_plan", {})
            entry_p = exec_plan.get("entry")
            sl_p = exec_plan.get("stop_loss")
            tp1_p = exec_plan.get("take_profit_1")
            tp2_p = exec_plan.get("take_profit_2")

            # Execute when:
            # - Direction is BULLISH_LONG or BEARISH_SHORT
            # - Setup is GRADE_A or GRADE_B
            # - Plan is not rejected
            is_executable = (
                direction in ["BULLISH_LONG", "BEARISH_SHORT"] and
                plan_status not in ["PLAN_REJECTED", "NO_SETUP"] and
                grade in ["GRADE_A", "GRADE_B"]
            )

            if not is_executable:
                logger.info("[AutoTrader] Standing by: Plan status is %s, grade is %s (%s)", plan_status, grade, analysis.get("handover_notes") or analysis.get("headline", ""))
                return {
                    "status": "WAITING",
                    "plan_status": plan_status,
                    "setup_grade": grade,
                    "message": analysis.get("handover_notes") or analysis.get("headline") or "Awaiting setup trigger condition"
                }

            if not entry_p or not sl_p:
                return {"status": "INVALID_LEVELS", "message": "Missing entry or stop loss parameters"}

            # ------------------------------------------------------------------
            # 4. LOT SIZING & RISK CALCULATION
            # ------------------------------------------------------------------
            account_summary = await self.oanda_client.get_account_summary() or {}
            balance = float(account_summary.get("balance", 10000.0))
            sl_dist = max(1.50, abs(entry_p - sl_p))

            lot_res = calculate_lot_size(
                account_balance=balance,
                risk_pct=self.risk_per_trade_pct,
                atr_m5=vol.get("atr_m5", 2.0),
                custom_sl_distance=sl_dist,
                current_price=price
            )

            # OANDA XAU_USD units: 1 unit = 1 ounce. Standard lot (1.0) = 100 units.
            # Clamp between 1 unit and 20 units (0.01 to 0.20 lots) for practice risk control
            calc_units = max(1, min(20, round(lot_res.calculated_lots * 100)))
            if direction == "BEARISH_SHORT":
                calc_units = -calc_units

            # ------------------------------------------------------------------
            # 5. DISPATCH ORDER TO OANDA PRACTICE ACCOUNT
            # ------------------------------------------------------------------
            order_res = await self.oanda_client.create_order(
                units=calc_units,
                stop_loss=sl_p,
                take_profit=tp2_p or tp1_p,
                entry_type="MARKET"
            )

            if not order_res:
                return {"status": "ORDER_FAILED", "message": "OANDA rejected order submission"}

            self.last_trade_time = now_ts

            # ------------------------------------------------------------------
            # 6. PERSIST TO TRADE JOURNAL
            # ------------------------------------------------------------------
            journal_entry = self.trade_journal.add_entry({
                "symbol": "XAU_USD",
                "session": frame.get("session", {}).get("active_session", "LONDON"),
                "killzone": frame.get("session", {}).get("killzone", "LONDON_OPEN"),
                "setup_grade": grade,
                "direction": direction,
                "confidence_pct": int(float(analysis.get("confidence_score", 0.8)) * 100),
                "entry_price": entry_p,
                "stop_loss": sl_p,
                "take_profit_1": tp1_p or 0.0,
                "take_profit_2": tp2_p or 0.0,
                "risk_distance_usd": round(sl_dist, 2),
                "account_balance": balance,
                "risk_pct": self.risk_per_trade_pct,
                "lot_size": lot_res.calculated_lots,
                "outcome": "OPEN",
                "confluence_factors": " • ".join(analysis.get("order_flow_breakdown", [])),
                "ai_thesis": analysis.get("thesis", ""),
                "notes": f"Auto-Executed to OANDA Practice Acc ({calc_units} units)."
            })

            logger.info("Auto-Trade successfully executed: %s %s units @ $%.2f | Journal ID: %s", direction, calc_units, entry_p, journal_entry.id)

            return {
                "status": "EXECUTED",
                "trade_id": journal_entry.id,
                "direction": direction,
                "units": calc_units,
                "lot_size": lot_res.calculated_lots,
                "entry_price": entry_p,
                "stop_loss": sl_p,
                "take_profit": tp2_p or tp1_p,
                "oanda_response": order_res
            }
