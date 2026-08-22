"""
Unit tests for Dynamic Risk & Position Sizing Calculator (src/core/risk_calculator.py).
"""
import pytest
from src.core.risk_calculator import calculate_lot_size, PositionSizeResult


def test_calculate_lot_size_standard():
    # Balance $10,000, 1% risk = $100
    # ATR_M5 = 2.0, Multiplier = 1.5 -> SL = $3.00
    # Lot size = $100 / ($3.00 * 100) = 100 / 300 = 0.33 lots
    result = calculate_lot_size(
        account_balance=10000.0,
        risk_pct=1.0,
        atr_m5=2.0,
        sl_multiplier=1.5,
        current_price=2935.0
    )

    assert result.account_balance == 10000.0
    assert result.risk_amount_usd == 100.0
    assert result.sl_distance_usd == 3.0
    assert result.calculated_lots == 0.33
    assert result.sl_price_long == 2932.0
    assert result.tp_1r_price == 2938.0
    assert result.tp_2r_price == 2941.0
    assert result.tp_3r_price == 2944.0


def test_calculate_lot_size_custom_sl():
    # Custom SL distance $5.00, Balance $5,000, 2% risk = $100
    # Lot size = 100 / (5.00 * 100) = 0.20 lots
    result = calculate_lot_size(
        account_balance=5000.0,
        risk_pct=2.0,
        custom_sl_distance=5.0
    )

    assert result.risk_amount_usd == 100.0
    assert result.sl_distance_usd == 5.0
    assert result.calculated_lots == 0.20


def test_calculate_lot_size_min_guard():
    # Very small balance -> should enforce min_lot_size of 0.01
    result = calculate_lot_size(
        account_balance=50.0,
        risk_pct=1.0,
        atr_m5=2.0
    )

    assert result.calculated_lots == 0.01


def test_result_to_dict():
    result = calculate_lot_size(10000.0, 1.0, 2.0, 1.5, current_price=2900.0)
    d = result.to_dict()
    assert d['account_balance'] == 10000.0
    assert d['calculated_lots'] == 0.33
    assert 'tp_2r_price' in d
