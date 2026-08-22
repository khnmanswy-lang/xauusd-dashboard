"""
Dynamic Risk & Position Sizing Engine for XAUUSD (Gold).
Calculates ATR-based dynamic stop loss, position sizing (lots), and risk-to-reward benchmarks.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class PositionSizeResult:
    """Calculated position sizing output."""
    account_balance: float
    risk_percentage: float
    risk_amount_usd: float
    atr_m5: float
    sl_multiplier: float
    sl_distance_usd: float
    calculated_lots: float
    min_lot_size: float
    contract_size_oz: float
    tp_1r_price: Optional[float] = None
    tp_2r_price: Optional[float] = None
    tp_3r_price: Optional[float] = None
    sl_price_long: Optional[float] = None
    sl_price_short: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_balance": round(self.account_balance, 2),
            "risk_percentage": round(self.risk_percentage, 2),
            "risk_amount_usd": round(self.risk_amount_usd, 2),
            "atr_m5": round(self.atr_m5, 2),
            "sl_multiplier": round(self.sl_multiplier, 2),
            "sl_distance_usd": round(self.sl_distance_usd, 2),
            "calculated_lots": self.calculated_lots,
            "min_lot_size": self.min_lot_size,
            "contract_size_oz": self.contract_size_oz,
            "sl_price_long": round(self.sl_price_long, 2) if self.sl_price_long is not None else None,
            "sl_price_short": round(self.sl_price_short, 2) if self.sl_price_short is not None else None,
            "tp_1r_price": round(self.tp_1r_price, 2) if self.tp_1r_price is not None else None,
            "tp_2r_price": round(self.tp_2r_price, 2) if self.tp_2r_price is not None else None,
            "tp_3r_price": round(self.tp_3r_price, 2) if self.tp_3r_price is not None else None
        }


def calculate_lot_size(
    account_balance: float = 10000.0,
    risk_pct: float = 1.0,
    atr_m5: float = 2.0,
    sl_multiplier: float = 1.5,
    custom_sl_distance: Optional[float] = None,
    current_price: Optional[float] = None,
    contract_size_oz: float = 100.0,
    min_lot_size: float = 0.01,
    max_lot_size: float = 100.0
) -> PositionSizeResult:
    """
    Calculate recommended lot size for XAUUSD.
    Formula:
    Risk Amount = Balance * (Risk % / 100)
    SL Distance ($) = custom_sl_distance or (sl_multiplier * ATR_M5)
    Lot Size = Risk Amount / (SL Distance * Contract Size)
    """
    # Guard against invalid or negative inputs
    safe_balance = max(0.0, account_balance)
    safe_risk_pct = max(0.01, min(risk_pct, 100.0))
    safe_atr = max(0.1, atr_m5)
    safe_multiplier = max(0.5, sl_multiplier)

    risk_amount_usd = safe_balance * (safe_risk_pct / 100.0)

    if custom_sl_distance is not None and custom_sl_distance > 0:
        sl_distance = custom_sl_distance
    else:
        sl_distance = safe_atr * safe_multiplier

    sl_distance = max(0.20, sl_distance)  # Minimum 20 cent SL distance

    raw_lot_size = risk_amount_usd / (sl_distance * contract_size_oz)
    calculated_lots = round(max(min_lot_size, min(raw_lot_size, max_lot_size)), 2)

    # Compute entry/exit reference prices if current price is provided
    sl_price_long = None
    sl_price_short = None
    tp_1r = None
    tp_2r = None
    tp_3r = None

    if current_price is not None and current_price > 0:
        sl_price_long = current_price - sl_distance
        sl_price_short = current_price + sl_distance
        tp_1r = current_price + sl_distance
        tp_2r = current_price + (2.0 * sl_distance)
        tp_3r = current_price + (3.0 * sl_distance)

    return PositionSizeResult(
        account_balance=safe_balance,
        risk_percentage=safe_risk_pct,
        risk_amount_usd=risk_amount_usd,
        atr_m5=safe_atr,
        sl_multiplier=safe_multiplier,
        sl_distance_usd=sl_distance,
        calculated_lots=calculated_lots,
        min_lot_size=min_lot_size,
        contract_size_oz=contract_size_oz,
        sl_price_long=sl_price_long,
        sl_price_short=sl_price_short,
        tp_1r_price=tp_1r,
        tp_2r_price=tp_2r,
        tp_3r_price=tp_3r
    )
