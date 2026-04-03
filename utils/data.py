"""
Market data fetching, indicator calculation, and Darvas Box detection.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta


# ─────────────────────── Data Fetching ───────────────────────
@st.cache_data(ttl=900, show_spinner=False)   # cache 15 min
def fetch_stock_data(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Fetch OHLCV data from Yahoo Finance for an NSE stock."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        df = ticker.history(period=period, interval="1d")
        if df.empty:
            return pd.DataFrame()
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.dropna(subset=["Close"], inplace=True)
        return df
    except Exception as e:
        st.error(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_nifty_data(period: str = "6mo") -> pd.DataFrame:
    """Fetch Nifty 50 index data."""
    try:
        ticker = yf.Ticker("^NSEI")
        df = ticker.history(period=period, interval="1d")
        if df.empty:
            return pd.DataFrame()
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame()


# ─────────────────── Indicator Calculation ───────────────────
def compute_indicators(df: pd.DataFrame, sma_period=50,
                       vol_avg_period=20, high_period=50,
                       low_period=50) -> pd.DataFrame:
    """
    Add trading indicators to OHLCV dataframe.
    
    Adds:  SMA50, High_50D, Low_50D, Avg_Vol_20,
           Vol_Ratio, Buy_Signal, Hard_SL
    """
    if df.empty or len(df) < sma_period:
        return df

    df = df.copy()

    # ── SMA 50 ──
    df["SMA50"] = df["Close"].rolling(window=sma_period, min_periods=20).mean()

    # ── 50-Day High (excluding current bar) — Darvas Box ceiling ──
    df["High_50D"] = df["High"].rolling(window=high_period, min_periods=10).max().shift(1)

    # ── 50-Day Low (including current bar) — Darvas Box floor ──
    df["Low_50D"] = df["Low"].rolling(window=low_period, min_periods=10).min()

    # ── 20-Day Average Volume ──
    df["Avg_Vol_20"] = df["Volume"].rolling(window=vol_avg_period, min_periods=5).mean()

    # ── Volume Ratio ──
    df["Vol_Ratio"] = np.where(
        df["Avg_Vol_20"] > 0, df["Volume"] / df["Avg_Vol_20"], 0
    )

    # ── Buy Signal: Close > 50D High  AND  Close > SMA50  AND  Vol > 1.5× ──
    df["Buy_Signal"] = (
        (df["Close"] > df["High_50D"]) &
        (df["Close"] > df["SMA50"]) &
        (df["Volume"] > 1.5 * df["Avg_Vol_20"])
    )

    # ── Hard Stop-Loss: 6 % below close on buy day ──
    df["Hard_SL"] = np.where(df["Buy_Signal"], df["Close"] * 0.94, np.nan)

    # ── Trailing Stop-Loss: 50-Day Low (only moves up) ──
    df["Trailing_SL"] = df["Low_50D"]

    # ── Sell / Exit signal: close drops below trailing SL ──
    df["Sell_Signal"] = (
        (df["Close"] < df["Low_50D"]) &
        (df["Close"] < df["SMA50"])
    )

    return df


# ─────────── Traditional Darvas Box Detection ───────────────
def find_darvas_boxes(df: pd.DataFrame, confirmation_days: int = 3):
    """
    Nicolas Darvas Box Theory implementation:
    
    1.  Stock makes a new recent high → potential box TOP
    2.  If high is NOT exceeded for `confirmation_days` → TOP confirmed
    3.  Find the lowest low during formation → potential box BOTTOM
    4.  If low is NOT broken for `confirmation_days` → BOTTOM confirmed
    5.  Box established [BOTTOM, TOP]
    6.  Breakout  = close > TOP   →  BUY
    7.  Breakdown = close < BOTTOM →  EXIT
    """
    if df.empty or len(df) < 20:
        return []

    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values
    dates = df.index
    n = len(df)
    boxes = []

    state = "LOOK"      # LOOK → CONFIRM_TOP → CONFIRM_BOT → ACTIVE
    pot_top = 0.0
    top_idx = 0
    confirm_count = 0
    pot_bot = float("inf")
    bot_confirm = 0
    box_start = 0

    for i in range(1, n):
        if state == "LOOK":
            if highs[i] >= highs[i - 1]:
                pot_top = highs[i]
                top_idx = i
                box_start = i
                confirm_count = 0
                state = "CONFIRM_TOP"

        elif state == "CONFIRM_TOP":
            if highs[i] > pot_top:
                pot_top = highs[i]
                top_idx = i
                confirm_count = 0
            else:
                confirm_count += 1
                if confirm_count >= confirmation_days:
                    pot_bot = min(lows[top_idx: i + 1])
                    bot_confirm = 0
                    state = "CONFIRM_BOT"

        elif state == "CONFIRM_BOT":
            if lows[i] < pot_bot:
                pot_bot = lows[i]
                bot_confirm = 0
            else:
                bot_confirm += 1
                if bot_confirm >= confirmation_days:
                    state = "ACTIVE"

        elif state == "ACTIVE":
            if closes[i] > pot_top:          # Breakout
                boxes.append({
                    "start": dates[box_start],
                    "end": dates[i],
                    "top": pot_top,
                    "bottom": pot_bot,
                    "breakout": True,
                    "break_idx": i,
                })
                pot_top = highs[i]
                top_idx = i
                box_start = i
                confirm_count = 0
                state = "CONFIRM_TOP"

            elif closes[i] < pot_bot:        # Breakdown
                boxes.append({
                    "start": dates[box_start],
                    "end": dates[i],
                    "top": pot_top,
                    "bottom": pot_bot,
                    "breakout": False,
                    "break_idx": i,
                })
                state = "LOOK"

    # Still-active box
    if state == "ACTIVE":
        boxes.append({
            "start": dates[box_start],
            "end": dates[-1],
            "top": pot_top,
            "bottom": pot_bot,
            "breakout": None,
            "break_idx": n - 1,
        })

    return boxes


# ────────────────── Nifty Bullish Check ─────────────────────
def check_nifty_bullish() -> dict:
    """Return whether Nifty 50 is above its 50-day SMA."""
    df = fetch_nifty_data("6mo")
    if df.empty or len(df) < 50:
        return {"bullish": False, "close": 0, "sma50": 0, "diff": 0}

    sma50 = df["Close"].rolling(50).mean().iloc[-1]
    close = df["Close"].iloc[-1]
    return {
        "bullish": close > sma50,
        "close": round(close, 2),
        "sma50": round(sma50, 2),
        "diff": round(close - sma50, 2),
    }


# ───────────────── Quick Scan All Stocks ────────────────────
def scan_stock(symbol: str) -> dict | None:
    """Scan one stock and return signal info or None."""
    df = fetch_stock_data(symbol, period="6mo")
    if df.empty or len(df) < 55:
        return None

    df = compute_indicators(df)
    latest = df.iloc[-1]

    if pd.isna(latest.get("SMA50")) or pd.isna(latest.get("High_50D")):
        return None

    result = {
        "symbol": symbol,
        "close": round(latest["Close"], 2),
        "sma50": round(latest["SMA50"], 2),
        "high_50d": round(latest["High_50D"], 2),
        "low_50d": round(latest["Low_50D"], 2),
        "volume": int(latest["Volume"]),
        "avg_vol": int(latest["Avg_Vol_20"]) if not pd.isna(latest["Avg_Vol_20"]) else 0,
        "vol_ratio": round(latest["Vol_Ratio"], 2),
        "buy_signal": bool(latest["Buy_Signal"]),
        "above_sma": latest["Close"] > latest["SMA50"],
        "breakout": latest["Close"] > latest["High_50D"],
    }
    return result
