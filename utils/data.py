"""
Data + Indicators — matches backtest exactly
Handles special characters in symbols like GVT&D and M&MFIN
"""

import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st


@st.cache_data(ttl=900, show_spinner=False)
def fetch_stock_data(symbol: str, period: str = "1y") -> pd.DataFrame:
    try:
        yahoo_symbol = symbol + ".NS"
        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(period=period, interval="1d")
        if df.empty:
            clean_symbol = symbol.replace("&", "").replace("-", "") + ".NS"
            ticker = yf.Ticker(clean_symbol)
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


def compute_indicators(df: pd.DataFrame, sma_period: int = 50) -> pd.DataFrame:
    """
    YOUR BACKTEST LOGIC:
        Box_Top     = df['High'].rolling(50).max().shift(1)
        Trailing_SL = df['Low'].rolling(50).min().shift(1)
        SMA         = df['Close'].rolling(sma_period).mean()
        Vol_SMA_20  = df['Volume'].rolling(20).mean()
    """
    if df.empty or len(df) < 20:
        return df

    df = df.copy()

    df["Box_Top"] = df["High"].rolling(window=50, min_periods=10).max().shift(1)

    df["Trailing_SL"] = df["Low"].rolling(window=50, min_periods=10).min().shift(1)

    df["SMA"] = df["Close"].rolling(window=sma_period, min_periods=min(20, sma_period)).mean()

    df["Vol_SMA_20"] = df["Volume"].rolling(window=20, min_periods=5).mean()

    df["Vol_Ratio"] = np.where(
        df["Vol_SMA_20"] > 0,
        df["Volume"] / df["Vol_SMA_20"],
        0
    )

    df["Buy_Signal"] = (
        (df["Close"] > df["Box_Top"]) &
        (df["Close"] > df["SMA"]) &
        (df["Volume"] > 1.5 * df["Vol_SMA_20"])
    )

    df["Sell_Signal"] = df["Low"] <= df["Trailing_SL"]

    df["Hard_SL"] = np.where(df["Buy_Signal"], df["Close"] * 0.94, np.nan)

    return df


def check_nifty_bullish() -> dict:
    """Nifty filter: YOUR BACKTEST uses SMA 100."""
    df = fetch_nifty_data("1y")
    if df.empty or len(df) < 100:
        return {"bullish": False, "close": 0, "sma100": 0, "sma50": 0, "diff": 0}

    sma100 = df["Close"].rolling(100).mean().iloc[-1]
    close = df["Close"].iloc[-1]
    return {
        "bullish": close > sma100,
        "close": round(close, 2),
        "sma100": round(sma100, 2),
        "sma50": round(sma100, 2),
        "diff": round(close - sma100, 2),
    }


def scan_stock(symbol: str, sma_period: int = 50):
    df = fetch_stock_data(symbol, period="6mo")
    if df.empty or len(df) < 55:
        return None

    df = compute_indicators(df, sma_period=sma_period)
    latest = df.iloc[-1]

    if pd.isna(latest.get("Box_Top")) or pd.isna(latest.get("SMA")):
        return None

    trail_sl = latest.get("Trailing_SL", 0)
    if pd.isna(trail_sl):
        trail_sl = 0

    vol_sma = latest.get("Vol_SMA_20", 0)
    if pd.isna(vol_sma):
        vol_sma = 0

    box_top = latest.get("Box_Top", 0)
    if pd.isna(box_top):
        box_top = 0

    return {
        "symbol": symbol,
        "close": round(latest["Close"], 2),
        "sma": round(latest["SMA"], 2),
        "high_50d": round(box_top, 2),
        "low_50d": round(trail_sl, 2),
        "volume": int(latest["Volume"]),
        "avg_vol": int(vol_sma),
        "vol_ratio": round(latest["Vol_Ratio"], 2),
        "buy_signal": bool(latest["Buy_Signal"]),
        "above_sma": bool(latest["Close"] > latest["SMA"]),
        "breakout": bool(latest["Close"] > box_top) if box_top > 0 else False,
    }
