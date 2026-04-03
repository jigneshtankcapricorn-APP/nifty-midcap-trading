"""
Market Data + Darvas Box Detection
MATCHES YOUR APP SCRIPT LOGIC EXACTLY
"""

import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st


# ═══════════════════ DATA FETCHING ═══════════════════

@st.cache_data(ttl=900, show_spinner=False)
def fetch_stock_data(symbol: str, period: str = "1y") -> pd.DataFrame:
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
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_nifty_data(period: str = "6mo") -> pd.DataFrame:
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


# ═══════════════════ INDICATORS (YOUR APP SCRIPT LOGIC) ═══════════════════

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    EXACT copy of your App Script calculations:

    1. SMA_50       = 50-day Simple Moving Average of Close
    2. High_50D     = Highest High of last 50 days EXCLUDING today (shifted by 1)
                      → This is the BREAKOUT level / box ceiling
    3. Low_50D      = Lowest Low of last 50 days INCLUDING today
                      → This is the TRAILING SL / box floor
    4. Avg_Vol_20   = 20-day Average Volume
    5. Vol_Ratio    = Today's Volume / Avg_Vol_20
    6. Buy_Signal   = Close > High_50D AND Close > SMA50 AND Volume > 1.5x Avg_Vol_20
    """
    if df.empty or len(df) < 20:
        return df

    df = df.copy()

    # ── SMA 50 ──
    # App Script: sma50Sum / sma50Period (using last 50 closes)
    df["SMA50"] = df["Close"].rolling(window=50, min_periods=20).mean()

    # ── 50-Day High EXCLUDING today ──
    # App Script: for (h = len-1-high50Period; h < len-1; h++) → excludes last bar
    # In pandas: rolling max then shift(1) to exclude current day
    df["High_50D"] = df["High"].rolling(window=50, min_periods=10).max().shift(1)

    # ── 50-Day Low INCLUDING today ──
    # App Script: for (l = len-low50Period; l < len; l++) → includes last bar
    df["Low_50D"] = df["Low"].rolling(window=50, min_periods=10).min()

    # ── 20-Day Average Volume ──
    # App Script: volSum / volAvgPeriod (using last 20 volumes)
    df["Avg_Vol_20"] = df["Volume"].rolling(window=20, min_periods=5).mean()

    # ── Volume Ratio ──
    df["Vol_Ratio"] = np.where(
        df["Avg_Vol_20"] > 0,
        df["Volume"] / df["Avg_Vol_20"],
        0
    )

    # ══════════════════════════════════════════════════
    # BUY SIGNAL — EXACT APP SCRIPT LOGIC:
    #   var breakout = close > high50d;
    #   var aboveSMA = close > sma50;
    #   var volumeSpike = volume > (avgVol20 * 1.5);
    #   if (breakout && aboveSMA && volumeSpike) → BUY
    # ══════════════════════════════════════════════════
    df["Buy_Signal"] = (
        (df["Close"] > df["High_50D"]) &          # Condition 1: breakout
        (df["Close"] > df["SMA50"]) &              # Condition 2: above SMA
        (df["Volume"] > 1.5 * df["Avg_Vol_20"])    # Condition 3: volume spike
    )

    # ── Hard Stop Loss = 6% below entry ──
    df["Hard_SL"] = np.where(df["Buy_Signal"], df["Close"] * 0.94, np.nan)

    # ══════════════════════════════════════════════════
    # TRAILING SL — EXACT APP SCRIPT LOGIC:
    #   var newTrailingSL = low50d;
    #   if (newTrailingSL < currentTrailingSL)
    #       newTrailingSL = currentTrailingSL; // NEVER lower
    # ══════════════════════════════════════════════════
    df["Trailing_SL"] = df["Low_50D"]

    # ══════════════════════════════════════════════════
    # EXIT SIGNAL — EXACT APP SCRIPT LOGIC:
    #   Active SL = MAX(Hard SL, Trailing SL)
    #   Exit when Close < Active SL OR Day Low < Active SL
    # ══════════════════════════════════════════════════
    df["Sell_Signal"] = df["Close"] < df["Low_50D"]

    return df


# ═══════════════════════════════════════════════════════════════
# DARVAS BOX DETECTION — BASED ON YOUR APP SCRIPT
# ═══════════════════════════════════════════════════════════════
#
#  Your app script creates boxes using 50D High and 50D Low:
#
#  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  50D High = Box Ceiling
#  ┃                   ┃
#  ┃  CONSOLIDATION    ┃  Price trades between ceiling and floor
#  ┃  ZONE = THE BOX   ┃  This can last days, weeks, or months
#  ┃                   ┃
#  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  50D Low = Box Floor
#
#  Close > 50D High → BREAKOUT (end of box, BUY direction) ✅
#  Close < 50D Low  → BREAKDOWN (end of box, EXIT direction) ❌
#
#  WHY BOXES HAVE DIFFERENT WIDTHS:
#  ─────────────────────────────────
#  Some stocks consolidate for 5 days, some for 50 days.
#  This is CORRECT and NATURAL. A wider box means:
#  → Longer consolidation → Potentially stronger breakout
#
#  WHY BOXES HAVE DIFFERENT HEIGHTS:
#  ─────────────────────────────────
#  Height = 50D High - 50D Low = the trading range
#  Volatile stocks → taller boxes
#  Quiet stocks → shorter boxes
#
# ═══════════════════════════════════════════════════════════════

def find_darvas_boxes(df: pd.DataFrame, min_box_days: int = 3) -> list:
    """
    Detect consolidation boxes using YOUR App Script's 50D High/Low logic.

    Each day is classified as:
    - INSIDE:    50D Low <= Close <= 50D High  (inside the box)
    - BREAKOUT:  Close > 50D High              (broke above ceiling)
    - BREAKDOWN: Close < 50D Low               (broke below floor)

    A BOX = consecutive INSIDE days.
    Box ends when BREAKOUT or BREAKDOWN happens.

    Parameters
    ----------
    df : DataFrame with High_50D and Low_50D columns (from compute_indicators)
    min_box_days : minimum candles for a valid box (default 3)

    Returns
    -------
    list of boxes, each with: start, end, top, bottom, breakout, candles, height_pct
    """
    if "High_50D" not in df.columns or "Low_50D" not in df.columns:
        return []

    valid = df.dropna(subset=["High_50D", "Low_50D"]).copy()
    if len(valid) < 10:
        return []

    closes = valid["Close"].values
    high_50d = valid["High_50D"].values
    low_50d = valid["Low_50D"].values
    dates = valid.index
    n = len(valid)

    boxes = []

    in_box = False
    box_start = 0
    box_top = 0.0
    box_bottom = float("inf")

    for i in range(n):
        # ── Classify today ──
        above_ceiling = closes[i] > high_50d[i]    # Breakout
        below_floor = closes[i] < low_50d[i]       # Breakdown
        inside_box = not above_ceiling and not below_floor  # Inside

        if not in_box:
            # ── Looking for new box ──
            if inside_box:
                # Start new consolidation box
                in_box = True
                box_start = i
                box_top = high_50d[i]
                box_bottom = low_50d[i]

        else:
            # ── Currently inside a box ──
            if inside_box:
                # Still inside — update box boundaries
                # Box top = highest 50D High during consolidation
                # Box bottom = lowest 50D Low during consolidation
                box_top = max(box_top, high_50d[i])
                box_bottom = min(box_bottom, low_50d[i])

            elif above_ceiling:
                # ═══ BREAKOUT! Close > 50D High ═══
                # This is your app script's BUY condition (condition 1 of 3)
                candle_count = i - box_start

                if candle_count >= min_box_days and box_top > box_bottom:
                    boxes.append({
                        "start": dates[box_start],
                        "end": dates[i],
                        "top": round(box_top, 2),
                        "bottom": round(box_bottom, 2),
                        "breakout": True,
                        "breakout_price": round(closes[i], 2),
                        "candles": candle_count,
                        "height_pct": round(
                            (box_top - box_bottom) / box_bottom * 100, 2
                        ) if box_bottom > 0 else 0,
                    })

                in_box = False

            elif below_floor:
                # ═══ BREAKDOWN! Close < 50D Low ═══
                # This is your app script's EXIT condition
                candle_count = i - box_start

                if candle_count >= min_box_days and box_top > box_bottom:
                    boxes.append({
                        "start": dates[box_start],
                        "end": dates[i],
                        "top": round(box_top, 2),
                        "bottom": round(box_bottom, 2),
                        "breakout": False,
                        "breakout_price": round(closes[i], 2),
                        "candles": candle_count,
                        "height_pct": round(
                            (box_top - box_bottom) / box_bottom * 100, 2
                        ) if box_bottom > 0 else 0,
                    })

                in_box = False

    # ── Active box (price still consolidating at end of data) ──
    if in_box:
        candle_count = (n - 1) - box_start
        if candle_count >= min_box_days and box_top > box_bottom:
            boxes.append({
                "start": dates[box_start],
                "end": dates[-1],
                "top": round(box_top, 2),
                "bottom": round(box_bottom, 2),
                "breakout": None,  # Still active, waiting for break
                "breakout_price": None,
                "candles": candle_count,
                "height_pct": round(
                    (box_top - box_bottom) / box_bottom * 100, 2
                ) if box_bottom > 0 else 0,
            })

    return boxes


# ═══════════════════ NIFTY BULLISH CHECK ═══════════════════

def check_nifty_bullish() -> dict:
    """
    YOUR APP SCRIPT LOGIC:
        var isBullish = currentClose > sma50;
    Only allow new buys when Nifty 50 is above its SMA 50.
    """
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


# ═══════════════════ STOCK SCANNER ═══════════════════

def scan_stock(symbol: str) -> dict | None:
    """Scan one stock using YOUR APP SCRIPT buy conditions."""
    df = fetch_stock_data(symbol, period="6mo")
    if df.empty or len(df) < 55:
        return None

    df = compute_indicators(df)
    latest = df.iloc[-1]

    if pd.isna(latest.get("SMA50")) or pd.isna(latest.get("High_50D")):
        return None

    return {
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
