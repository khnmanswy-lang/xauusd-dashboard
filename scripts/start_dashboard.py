#!/usr/bin/env python3
"""
Dashboard Launcher Script for Real-Time XAUUSD Multi-Timeframe Terminal.
Starts FastAPI backend server, initializes live data feeds, and launches browser UI.
"""
import argparse
import sys
import webbrowser
from pathlib import Path

# Ensure project root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from src.config.settings import settings


def main():
    parser = argparse.ArgumentParser(description="Launch Real-Time XAUUSD Multi-Timeframe Terminal")
    parser.add_argument("--host", default=settings.host, help=f"Host address (default: {settings.host})")
    parser.add_argument("--port", type=int, default=settings.port, help=f"Port number (default: {settings.port})")
    parser.add_argument("--reload", action="store_true", default=settings.reload, help="Enable auto-reload on code change")
    parser.add_argument("--no-browser", action="store_true", help="Do not open local browser automatically")

    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print("=" * 70)
    print("⚡  XAUUSD REAL-TIME MULTI-TIMEFRAME TRADING TERMINAL  ⚡")
    print("=" * 70)
    print(f"  • Dashboard UI:        {url}")
    print(f"  • WebSocket Stream:    {url}/ws/stream")
    print(f"  • REST State API:      {url}/api/state")
    print(f"  • Economic News API:   {url}/api/news")
    print("=" * 70)
    print("Starting server... Press Ctrl+C to stop.")

    if not args.no_browser and args.host in ("127.0.0.1", "localhost", "0.0.0.0"):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run("src.server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
