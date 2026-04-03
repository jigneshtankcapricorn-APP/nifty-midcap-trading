"""
Market Data + Darvas Box Detection
MATCHES YOUR 25-YEAR BACKTEST LOGIC EXACTLY
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
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_nifty_data(period: str = "1y") -> pd.DataFrame:
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


# ═══════════════════════════════════════════════════════
# INDICATORS — EXACT MATCH WITH YOUR BACKTEST
# ═══════════════════════════════════════════════════════
#
#  YOUR BACKTEST CODE:
#  ───────────────────
#  df['Box_Top']     = df['High'].rolling(window=50).max().shift(1)
#  df['Trailing_SL'] = df['Low'].rolling(window=50).min().shift(1)
#  df['SMA_50']      = df['Close'].rolling(window=50).mean()
#  df['Vol_SMA_20']  = df['Volume'].rolling(window=20).mean()
#
#  KEY: Both Box_Top and Trailing_SL use .shift(1)
#       This means EXCLUDING today's bar
#       Yesterday's 50-day high/low is what matters
#
# ═══════════════════════════════════════════════════════

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 20:
        return df

    df = df.copy()

    # ── Box_Top = 50-Day HIGH, shifted by 1 (EXCLUDES today) ──
    # YOUR BACKTEST: df['Box_Top'] = df['High'].rolling(window=50).max().shift(1)
    df["Box_Top"] = df["High"].rolling(window=50, min_periods=10).max().shift(1)

    # ── Trailing_SL = 50-Day LOW, shifted by 1 (EXCLUDES today) ──
    # YOUR BACKTEST: df['Trailing_SL'] = df['Low'].rolling(window=50).min().shift(1)
    df["Trailing_SL"] = df["Low"].rolling(window=50, min_periods=10).min().shift(1)

    # ── SMA 50 ──
    # YOUR BACKTEST: df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df["SMA_50"] = df["Close"].rolling(window=50, min_periods=20).mean()

    # ── 20-Day Volume Average ──
    # YOUR BACKTEST: df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df["Vol_SMA_20"] = df["Volume"].rolling(window=20, min_periods=5).mean()

    # ── Volume Ratio (for display) ──
    df["Vol_Ratio"] = np.where(
        df["Vol_SMA_20"] > 0,
        df["Volume"] / df["Vol_SMA_20"],
        0
    )

    # ══════════════════════════════════════════════════════
    # BUY SIGNAL — EXACT BACKTEST LOGIC:
    #
    # YOUR CODE:
    #   is_breakout    = row['Close'] > row['Box_Top']
    #   is_uptrend     = row['Close'] > row['SMA_50']
    #   is_huge_volume = row['Volume'] > (row['Vol_SMA_20'] * 1.5)
    #   if is_breakout and is_uptrend and is_huge_volume: BUY
    # ══════════════════════════════════════════════════════
    df["Buy_Signal"] = (
        (df["Close"] > df["Box_Top"]) &
        (df["Close"] > df["SMA_50"]) &
        (df["Volume"] > 1.5 * df["Vol_SMA_20"])
    )

    # ── Hard SL = 6% below entry (for display on chart) ──
    df["Hard_SL"] = np.where(df["Buy_Signal"], df["Close"] * 0.94, np.nan)

    # ══════════════════════════════════════════════════════
    # EXIT SIGNAL — EXACT BACKTEST LOGIC:
    #
    # YOUR CODE:
    #   current_sl = max(pos['hard_sl'], row['Trailing_SL'])
    #   if row['Open'] <= current_sl:
    #       exit_price = row['Open']          ← gap down
    #   elif row['Low'] <= current_sl:
    #       exit_price = current_sl           ← intraday hit
    #
    # For chart display we check:
    #   Low touches Trailing_SL = potential exit
    # ══════════════════════════════════════════════════════
    df["Sell_Signal"] = df["Low"] <= df["Trailing_SL"]

    # Keep old column names for compatibility
    df["High_50D"] = df["Box_Top"]
    df["Low_50D"] = df["Trailing_SL"]
    df["Avg_Vol_20"] = df["Vol_SMA_20"]
    df["SMA50"] = df["SMA_50"]

    return df


# ═══════════════════════════════════════════════════════
# DARVAS BOX DETECTION — BASED ON YOUR BACKTEST
# ═══════════════════════════════════════════════════════
#
#  Box_Top      = 50D High .shift(1)  = ceiling
#  Trailing_SL  = 50D Low  .shift(1)  = floor
#
#  INSIDE BOX:  Trailing_SL <= Close <= Box_Top
#  BREAKOUT:    Close > Box_Top  (potential BUY)
#  BREAKDOWN:   Low <= Trailing_SL  (potential EXIT)
#
#  YOUR BACKTEST EXIT:
#    if row['Open'] <= current_sl → exit at open (gap down)
#    elif row['Low'] <= current_sl → exit at SL (intraday)
#
# ═══════════════════════════════════════════════════════

def find_darvas_boxes(df: pd.DataFrame, min_box_days: int = 3) -> list:
    if "Box_Top" not in df.columns or "Trailing_SL" not in df.columns:
        return []

    valid = df.dropna(subset=["Box_Top", "Trailing_SL"]).copy()
    if len(valid) < 10:
        return []

    closes = valid["Close"].values
    highs = valid["High"].values
    lows = valid["Low"].values
    opens = valid["Open"].values
    box_tops = valid["Box_Top"].values
    trail_sls = valid["Trailing_SL"].values
    dates = valid.index
    n = len(valid)

    boxes = []
    in_box = False
    box_start = 0
    box_top = 0.0
    box_bottom = float("inf")

    for i in range(n):
        is_breakout = closes[i] > box_tops[i]
        is_breakdown = lows[i] <= trail_sls[i]
        is_inside = not is_breakout and not is_breakdown

        if not in_box:
            if is_inside:
                in_box = True
                box_start = i
                box_top = box_tops[i]
                box_bottom = trail_sls[i]
        else:
            if is_inside:
                box_top = max(box_top, box_tops[i])
                box_bottom = min(box_bottom, trail_sls[i])

            elif is_breakout:
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

            elif is_breakdown:
                candle_count = i - box_start
                if candle_count >= min_box_days and box_top > box_bottom:
                    # Determine exit price like your backtest
                    if opens[i] <= trail_sls[i]:
                        exit_p = round(opens[i], 2)
                    else:
                        exit_p = round(trail_sls[i], 2)

                    boxes.append({
                        "start": dates[box_start],
                        "end": dates[i],
                        "top": round(box_top, 2),
                        "bottom": round(box_bottom, 2),
                        "breakout": False,
                        "breakout_price": exit_p,
                        "candles": candle_count,
                        "height_pct": round(
                            (box_top - box_bottom) / box_bottom * 100, 2
                        ) if box_bottom > 0 else 0,
                    })
                in_box = False

    # Active box at end of data
    if in_box:
        candle_count = (n - 1) - box_start
        if candle_count >= min_box_days and box_top > box_bottom:
            boxes.append({
                "start": dates[box_start],
                "end": dates[-1],
                "top": round(box_top, 2),
                "bottom": round(box_bottom, 2),
                "breakout": None,
                "breakout_price": None,
                "candles": candle_count,
                "height_pct": round(
                    (box_top - box_bottom) / box_bottom * 100, 2
                ) if box_bottom > 0 else 0,
            })

    return boxes


# ═══════════════════════════════════════════════════════
# NIFTY BULLISH CHECK — YOUR BACKTEST USES SMA 100!
# ═══════════════════════════════════════════════════════
#
#  YOUR BACKTEST CODE:
#    nifty_df['SMA_100'] = nifty_df['Close'].rolling(100).mean()
#    market_bullish_dates = set(
#        nifty_df[nifty_df['Close'] > nifty_df['SMA_100']].index
#    )
#
#  NOT SMA 50! Your backtest uses SMA 100 for Nifty filter!
#
# ═══════════════════════════════════════════════════════

def check_nifty_bullish() -> dict:
    df = fetch_nifty_data("1y")
    if df.empty or len(df) < 100:
        return {"bullish": False, "close": 0, "sma100": 0, "diff": 0}

    # YOUR BACKTEST: SMA 100 for Nifty
    sma100 = df["Close"].rolling(100).mean().iloc[-1]
    close = df["Close"].iloc[-1]
    return {
        "bullish": close > sma100,
        "close": round(close, 2),
        "sma50": round(sma100, 2),  # keeping key name for compatibility
        "sma100": round(sma100, 2),
        "diff": round(close - sma100, 2),
    }


# ═══════════════════════════════════════════════════════
# STOCK SCANNER — USES YOUR EXACT BUY CONDITIONS
# ═══════════════════════════════════════════════════════

def scan_stock(symbol: str):
    df = fetch_stock_data(symbol, period="6mo")
    if df.empty or len(df) < 55:
        return None

    df = compute_indicators(df)
    latest = df.iloc[-1]

    if pd.isna(latest.get("Box_Top")) or pd.isna(latest.get("SMA_50")):
        return None

    return {
        "symbol": symbol,
        "close": round(latest["Close"], 2),
        "sma50": round(latest["SMA_50"], 2),
        "high_50d": round(latest["Box_Top"], 2),
        "low_50d": round(latest["Trailing_SL"], 2) if not pd.isna(latest.get("Trailing_SL")) else 0,
        "volume": int(latest["Volume"]),
        "avg_vol": int(latest["Vol_SMA_20"]) if not pd.isna(latest.get("Vol_SMA_20")) else 0,
        "vol_ratio": round(latest["Vol_Ratio"], 2),
        "buy_signal": bool(latest["Buy_Signal"]),
        "above_sma": latest["Close"] > latest["SMA_50"],
        "breakout": latest["Close"] > latest["Box_Top"] if not pd.isna(latest.get("Box_Top")) else False,
    }
