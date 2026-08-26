"""
Smart Cron Sentry CLI for Antigravity Autonomous Agent.
Executes in one fast pass:
1. Pulls live tick, session levels, VWAP, ADR, sweeps, and FVGs.
2. Manages running OANDA practice trades (auto-trailing SL to Break-Even at +1.5R).
3. Evaluates pending setup plan and triggers.
4. Returns concise, noise-filtered, smart markdown output:
   - 1-line compact HUD if standing aside / no state change.
   - Full institutional action card when an execution, sweep, or plan shift occurs.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
import urllib.request

from src.config.settings import settings
from src.integrations.oanda_client import OandaClient

STATE_FILE = "data/cron_sentry_state.json"


def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_previous_state(state):
    os.makedirs("data", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


async def run_smart_sentry():
    prev_state = load_previous_state()
    iteration = prev_state.get("iteration", 0) + 1
    
    # 1. Fetch live server state
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/state", headers={"User-Agent": "CronSentry/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as res:
            live_state = json.loads(res.read())
    except Exception as e:
        print(f"⚠️ **[CRON #{iteration}] Server Offline:** Could not reach `http://127.0.0.1:8000/api/state` ({e})")
        return

    price = live_state.get("xauusd", {}).get("price", 0.0)
    spread = live_state.get("xauusd", {}).get("spread", 0.0)
    session = live_state.get("session", {})
    volatility = live_state.get("volatility", {})
    setup_scan = live_state.get("setup_scan", {})
    recent_sweep = session.get("recent_sweep", "NONE")
    adr_pct = volatility.get("adr_used_pct", 0.0)
    m5_timer = live_state.get("xauusd", {}).get("candle_timer_m5", 300)
    m5_min = m5_timer // 60
    m5_sec = m5_timer % 60

    # 2. Check OANDA practice account & Trailing Stop Management
    oanda = OandaClient(settings.oanda)
    open_trades = []
    trailing_action = None
    if oanda.is_configured():
        try:
            open_trades = await oanda.get_open_trades()
            for t in open_trades:
                tid = t.get("id")
                units = float(t.get("currentUnits", 0))
                entry_p = float(t.get("price", 0))
                curr_sl = float(t.get("stopLossOrder", {}).get("price", 0)) if "stopLossOrder" in t else None
                is_long = units > 0
                gain = (price - entry_p) if is_long else (entry_p - price)
                
                if gain >= 3.00:
                    be_sl = round(entry_p + 0.50 if is_long else entry_p - 0.50, 2)
                    if curr_sl is None or (is_long and curr_sl < be_sl) or (not is_long and curr_sl > be_sl):
                        success = await oanda.update_stop_loss(tid, be_sl)
                        if success:
                            trailing_action = f"🛡️ Trailed SL for Trade #{tid} to Break-Even (${be_sl:.2f}, Gain: +${gain:.2f})"
        except Exception:
            pass

    # 3. Detect significant event vs baseline
    last_sweep = prev_state.get("last_sweep", "NONE")
    last_grade = prev_state.get("last_grade", "NO_SETUP")
    curr_grade = setup_scan.get("grade", "NO_SETUP")
    curr_status = setup_scan.get("direction", "NEUTRAL")

    has_event = (
        trailing_action is not None
        or (recent_sweep != "NONE" and recent_sweep != last_sweep)
        or (curr_grade != "NO_SETUP" and curr_grade != last_grade)
        or (len(open_trades) != prev_state.get("open_trades_count", 0))
    )

    # 4. Save state
    save_previous_state({
        "iteration": iteration,
        "last_price": price,
        "last_sweep": recent_sweep,
        "last_grade": curr_grade,
        "open_trades_count": len(open_trades),
        "timestamp": int(datetime.now(timezone.utc).timestamp())
    })

    # 5. Adaptive Output: Minimal Heartbeat vs Rich Action Card
    if not has_event and len(open_trades) == 0:
        guard_note = f"ADR Exhausted ({adr_pct:.0f}%)" if adr_pct >= 80 else "Consolidating"
        print(f"`[CRON #{iteration:02d} • {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC]` 🟡 **STAND ASIDE:** Gold `${price:.2f}` (Spread `${spread:.2f}`) | Session: `{session.get('active_session')}` | `{guard_note}` | OANDA: `0 Pos` | M5 Bar: `{m5_min:02d}:{m5_sec:02d}`")
    else:
        print(f"### ⚡ Antigravity Cron [Iteration #{iteration:02d}] Action Report")
        if trailing_action:
            print(f"> **{trailing_action}**\n")
        
        print(f"| Metric | Live Value | Regime / Status |")
        print(f"|---|---|---|")
        print(f"| **Spot Price** | **`${price:.2f}`** (Spread `${spread:.2f}`) | `{session.get('active_session')}` ({session.get('killzone')}) |")
        print(f"| **Liquidity Sweep** | **`{recent_sweep}`** | Range: `${session.get('asia_low', 0):.2f} - ${session.get('asia_high', 0):.2f}` |")
        print(f"| **Setup Scan** | **`{curr_grade}` ({curr_status})** | Confidence: `{setup_scan.get('confidence_score', 0)*100:.0f}%` |")
        print(f"| **ADR Used** | **`{adr_pct:.1f}%`** | {'⚠️ Ceiling Active' if adr_pct >= 80 else '✅ Expansion Available'} |")
        print(f"| **OANDA Active** | **`{len(open_trades)} Open Positions`** | Idempotency Checked |")
        
        if setup_scan.get("suggested_entry"):
            print(f"\n🎯 **Playable Setup:** Entry `${setup_scan.get('suggested_entry'):.2f}` | SL `${setup_scan.get('suggested_sl'):.2f}` | TP1 `${setup_scan.get('suggested_tp1'):.2f}` | TP2 `${setup_scan.get('suggested_tp2'):.2f}` (R:R `1:{setup_scan.get('risk_reward_ratio', 0):.2f}`)")


if __name__ == "__main__":
    asyncio.run(run_smart_sentry())
