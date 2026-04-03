"""
NIFTY MIDCAP 150 — DARVAS BOX TRADING SYSTEM
v2.1 — Lines Only, SMA Selector, Nifty Warning Mode
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from utils.constants import CONFIG, STOCK_LIST, SECTORS
from utils.data import (
    fetch_stock_data,
    compute_indicators,
    check_nifty_bullish,
    scan_stock,
)
from utils.charts import create_darvas_chart

st.set_page_config(
    page_title="Midcap 150 Darvas Trading",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css():
    st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1b2a 0%, #1b2838 100%);
    }
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a1f2e, #252b3b);
        border: 1px solid #333;
        border-radius: 10px;
        padding: 12px 16px;
    }
    div[data-testid="metric-container"] label {
        color: #90CAF9 !important;
    }
    .header-bar {
        background: linear-gradient(90deg, #1a3c7a, #4472c4);
        padding: 18px 28px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .header-bar h1 { color: white; margin: 0; font-size: 1.6rem; }
    .header-bar p { color: #bbdefb; margin: 4px 0 0 0; font-size: 0.9rem; }
    .nifty-warning {
        background: #4a1c1c;
        border: 1px solid #ff5252;
        border-radius: 8px;
        padding: 10px 16px;
        color: #ff8a80;
        font-weight: 600;
        margin: 8px 0;
    }
    .nifty-ok {
        background: #1b3a1b;
        border: 1px solid #4caf50;
        border-radius: 8px;
        padding: 10px 16px;
        color: #81c784;
        font-weight: 600;
        margin: 8px 0;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)


def init_state():
    defaults = {
        "logged_in": False,
        "selected_stock": "TRENT",
        "portfolio": [],
        "trade_log": [],
        "signals_log": [],
        "page": "Dashboard",
        "last_scan": [],
        "sma_period": 50,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def login_page():
    st.markdown("")
    st.markdown("")
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown(
            "<div style='text-align:center;'>"
            "<h1 style='color:#4FC3F7;'>📈 Midcap 150</h1>"
            "<h3 style='color:#90CAF9;'>Darvas Box Trading System</h3>"
            "<p style='color:#78909C;'>Enter credentials to continue</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")
        username = st.text_input("Username", placeholder="Enter username", key="login_user")
        password = st.text_input("Password", type="password", placeholder="Enter password", key="login_pass")
        st.markdown("")
        if st.button("Login", use_container_width=True, type="primary"):
            try:
                valid_user = st.secrets["credentials"]["username"]
                valid_pwd = st.secrets["credentials"]["password"]
            except Exception:
                valid_user = "admin"
                valid_pwd = "admin"
            if username == valid_user and password == valid_pwd:
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("Invalid username or password")
        st.caption("Default: admin / admin (if secrets not set)")


def get_nifty_warning_html(nifty):
    """Return HTML warning or OK banner for Nifty status."""
    if nifty["bullish"]:
        return (
            "<div class='nifty-ok'>"
            "✅ NIFTY 50 UPTREND — Safe to take new positions | "
            f"Close: Rs{nifty['close']:,.0f} > SMA100: Rs{nifty['sma100']:,.0f} | "
            f"Above by {nifty['diff']:+,.0f}"
            "</div>"
        )
    else:
        return (
            "<div class='nifty-warning'>"
            "⚠️ WARNING: NIFTY 50 IN DOWNTREND — Buy signals shown but trade at your own risk! | "
            f"Close: Rs{nifty['close']:,.0f} < SMA100: Rs{nifty['sma100']:,.0f} | "
            f"Below by {nifty['diff']:,.0f}"
            "</div>"
        )


def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center; padding:10px 0 20px;'>"
            "<h2 style='color:#4FC3F7; margin:0;'>📈 Darvas Trading</h2>"
            "<p style='color:#78909C; font-size:0.8rem; margin:0;'>Midcap 150 System</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        pages = ["Dashboard", "Charts", "Stock Scanner", "Portfolio", "Signals Log", "Trade Log", "Settings"]
        icons = ["📊", "📈", "🔍", "💼", "📋", "📜", "⚙️"]
        for i, page in enumerate(pages):
            if st.button(f"{icons[i]} {page}", use_container_width=True, key=f"nav_{page}"):
                st.session_state["page"] = page

        st.divider()

        # ── SMA PERIOD SELECTOR ──
        st.markdown("**📐 SMA Period**")
        sma_choice = st.radio(
            "Choose SMA for trend filter",
            options=[50, 100],
            index=0 if st.session_state["sma_period"] == 50 else 1,
            horizontal=True,
            key="sma_radio",
        )
        st.session_state["sma_period"] = sma_choice
        st.caption(f"Buy condition: Close > SMA {sma_choice}")

        st.divider()

        # ── NIFTY STATUS ──
        nifty = check_nifty_bullish()
        if nifty["bullish"]:
            st.success(f"NIFTY 50: Rs{nifty['close']:,.0f} BULLISH")
        else:
            st.error(f"NIFTY 50: Rs{nifty['close']:,.0f} BEARISH")
        st.caption(f"SMA100: Rs{nifty['sma100']:,.0f} | Diff: {nifty['diff']:+,.0f}")

        st.divider()

        # ── QUICK STOCK SELECT ──
        symbols = [s["symbol"] for s in STOCK_LIST]
        idx = symbols.index(st.session_state["selected_stock"]) if st.session_state["selected_stock"] in symbols else 0
        chosen = st.selectbox("Quick Stock Select", symbols, index=idx)
        if chosen != st.session_state["selected_stock"]:
            st.session_state["selected_stock"] = chosen
        if st.button("View Chart", use_container_width=True, type="primary"):
            st.session_state["page"] = "Charts"
            st.rerun()

        st.divider()
        if st.button("Logout", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()


def page_dashboard():
    st.markdown(
        "<div class='header-bar'><h1>📊 Dashboard</h1>"
        "<p>Nifty Midcap 150 Darvas Trading System</p></div>",
        unsafe_allow_html=True,
    )

    # Nifty Status Banner
    nifty = check_nifty_bullish()
    st.markdown(get_nifty_warning_html(nifty), unsafe_allow_html=True)

    try:
        capital = st.secrets["trading"]["capital"]
        max_legs = st.secrets["trading"]["max_legs"]
        per_leg = st.secrets["trading"]["per_leg_pct"]
        hard_sl = st.secrets["trading"]["hard_sl_pct"]
    except Exception:
        capital = 200000
        max_legs = 5
        per_leg = 0.20
        hard_sl = 0.06

    st.subheader("System Status")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Capital", f"Rs{capital:,.0f}")
    c2.metric("Per Leg", f"Rs{capital * per_leg:,.0f}")
    c3.metric("Max Legs", max_legs)
    c4.metric("Hard SL", f"{hard_sl * 100:.0f}%")
    c5.metric("SMA Filter", f"SMA {st.session_state['sma_period']}")

    st.divider()
    st.subheader("Portfolio Summary")
    portfolio = st.session_state.get("portfolio", [])
    active = [p for p in portfolio if p.get("status") == "ACTIVE"]
    total_invested = sum(p.get("invested", 0) for p in active)
    total_current = sum(p.get("current_value", 0) for p in active)
    total_pnl = total_current - total_invested
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Active Positions", f"{len(active)} / {max_legs}")
    p2.metric("Total Invested", f"Rs{total_invested:,.0f}")
    p3.metric("Current Value", f"Rs{total_current:,.0f}")
    pnl_delta = f"{(total_pnl / total_invested * 100):.1f}%" if total_invested else "0%"
    p4.metric("Unrealized PnL", f"Rs{total_pnl:,.0f}", delta=pnl_delta)

    st.divider()
    st.subheader("Trade Statistics")
    log = st.session_state.get("trade_log", [])
    wins = [t for t in log if t.get("pnl", 0) > 0]
    losses = [t for t in log if t.get("pnl", 0) <= 0]
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Total Trades", len(log))
    t2.metric("Winners", len(wins))
    t3.metric("Losers", len(losses))
    t4.metric("Win Rate", f"{len(wins) / len(log) * 100:.0f}%" if log else "N/A")

    st.divider()
    st.subheader("Quick Actions")
    qa1, qa2, qa3 = st.columns(3)
    with qa1:
        if st.button("Run Stock Scanner", use_container_width=True, type="primary"):
            st.session_state["page"] = "Stock Scanner"
            st.rerun()
    with qa2:
        if st.button("Open Charts", use_container_width=True):
            st.session_state["page"] = "Charts"
            st.rerun()
    with qa3:
        if st.button("View Portfolio", use_container_width=True):
            st.session_state["page"] = "Portfolio"
            st.rerun()


def page_charts():
    st.markdown(
        "<div class='header-bar'><h1>📈 Chart Analysis</h1>"
        "<p>Darvas Breakout Lines with SMA Filter</p></div>",
        unsafe_allow_html=True,
    )

    nifty = check_nifty_bullish()
    st.markdown(get_nifty_warning_html(nifty), unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbols = [s["symbol"] for s in STOCK_LIST]
        current = st.session_state["selected_stock"]
        idx = symbols.index(current) if current in symbols else 0
        selected = st.selectbox("Select Stock", symbols, index=idx)
        if selected != st.session_state["selected_stock"]:
            st.session_state["selected_stock"] = selected
            st.rerun()
    with col2:
        period = st.selectbox("Period", ["6mo", "1y", "2y", "5y"], index=1)
    with col3:
        show_bands = st.checkbox("Show 50D Lines", value=True)

    symbol = st.session_state["selected_stock"]
    sma_period = st.session_state["sma_period"]
    stock_info = next((s for s in STOCK_LIST if s["symbol"] == symbol), {})

    with st.spinner(f"Loading {symbol} ({stock_info.get('name', '')})..."):
        df = fetch_stock_data(symbol, period=period)

    if df.empty:
        st.error(f"Could not load data for {symbol}. Try again.")
        return

    df = compute_indicators(df, sma_period=sma_period)

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    change = latest["Close"] - prev["Close"]
    pct = change / prev["Close"] * 100

    # Stock name header
    st.markdown(
        f"**{symbol}** — {stock_info.get('name', '')} | "
        f"Sector: {stock_info.get('sector', 'N/A')}"
    )

    i1, i2, i3, i4, i5, i6 = st.columns(6)
    i1.metric("Price", f"Rs{latest['Close']:,.2f}", f"{change:+,.2f} ({pct:+.2f}%)")
    i2.metric("Open", f"Rs{latest['Open']:,.2f}")
    i3.metric("High", f"Rs{latest['High']:,.2f}")
    i4.metric("Low", f"Rs{latest['Low']:,.2f}")
    i5.metric("Volume", f"{latest['Volume']:,.0f}")
    sma_val = latest.get("SMA", 0)
    i6.metric(f"SMA {sma_period}", f"Rs{sma_val:,.2f}" if not pd.isna(sma_val) else "N/A")

    fig = create_darvas_chart(
        df, symbol,
        show_signals=True,
        show_bands=show_bands,
        sma_period=sma_period,
        nifty_bullish=nifty["bullish"],
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(f"#### Buy Signals (Last 30 Days) — SMA {sma_period}")
        recent = df.tail(30)
        if "Buy_Signal" in recent.columns:
            buy_days = recent[recent["Buy_Signal"] == True]
            if buy_days.empty:
                st.info("No buy signals in last 30 days")
            else:
                for dt, row in buy_days.iterrows():
                    sl = row["Close"] * 0.94
                    nifty_tag = "" if nifty["bullish"] else " ⚠️ NIFTY DOWN"
                    st.markdown(
                        f"**{dt.strftime('%d-%b-%Y')}** — "
                        f"Rs{row['Close']:,.2f} | "
                        f"Vol: {row['Vol_Ratio']:.1f}x | "
                        f"SL: Rs{sl:,.2f}{nifty_tag}"
                    )
        else:
            st.info("No signal data")

    with col_right:
        st.markdown("#### Current Levels")
        if "Box_Top" in df.columns and not pd.isna(latest.get("Box_Top")):
            box_top = latest["Box_Top"]
            trail_sl = latest.get("Trailing_SL", 0)
            sma = latest.get("SMA", 0)
            close = latest["Close"]

            st.markdown(f"**Breakout Level (50D High):** Rs{box_top:,.2f}")
            if close > box_top:
                st.success(f"Price Rs{close:,.2f} is ABOVE breakout level")
            else:
                gap = ((box_top - close) / close) * 100
                st.info(f"Price Rs{close:,.2f} is {gap:.1f}% below breakout")

            if not pd.isna(trail_sl) and trail_sl > 0:
                st.markdown(f"**Trailing SL (50D Low):** Rs{trail_sl:,.2f}")
                buffer_pct = ((close - trail_sl) / close) * 100
                st.markdown(f"Buffer from SL: {buffer_pct:.1f}%")

            if not pd.isna(sma):
                st.markdown(f"**SMA {sma_period}:** Rs{sma:,.2f}")
                if close > sma:
                    st.success(f"Price ABOVE SMA {sma_period} — Uptrend")
                else:
                    st.warning(f"Price BELOW SMA {sma_period} — Downtrend")

            st.markdown(f"**Hard SL (if buy today):** Rs{close * 0.94:,.2f} (-6%)")
        else:
            st.info("Not enough data for levels")

    # Quick Navigation — FIXED to properly load chart
    st.divider()
    st.markdown("#### Quick Navigation — Click any stock to load chart")
    sector_filter = st.selectbox("Filter by Sector", ["All"] + SECTORS, key="sector_nav")
    display_stocks = STOCK_LIST
    if sector_filter != "All":
        display_stocks = [s for s in STOCK_LIST if s["sector"] == sector_filter]

    # Show current selected stock highlighted
    st.caption(f"Currently viewing: **{symbol}**")

    cols = st.columns(8)
    for j, stk in enumerate(display_stocks):
        with cols[j % 8]:
            # Highlight current stock
            btn_type = "primary" if stk["symbol"] == symbol else "secondary"
            if st.button(
                stk["symbol"],
                key=f"nav_{stk['symbol']}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state["selected_stock"] = stk["symbol"]
                st.rerun()

def page_scanner():
    st.markdown(
        "<div class='header-bar'><h1>🔍 Stock Scanner</h1>"
        "<p>Scan Nifty Midcap 150 for breakout signals</p></div>",
        unsafe_allow_html=True,
    )

    # Nifty Warning Banner
    nifty = check_nifty_bullish()
    st.markdown(get_nifty_warning_html(nifty), unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])
    with col1:
        filter_sector = st.multiselect("Filter by Sector", SECTORS, default=[])
    with col2:
        filter_type = st.radio("Show", ["All", "Buy Signals Only", "Above SMA", "Breakout"], horizontal=True)

    sma_period = st.session_state["sma_period"]
    st.caption(f"Using SMA {sma_period} for trend filter | Nifty filter: {'BULLISH' if nifty['bullish'] else 'BEARISH (signals still shown with warning)'}")

    if st.button("Run Full Scan", type="primary"):
        filtered = STOCK_LIST
        if filter_sector:
            filtered = [s for s in filtered if s["sector"] in filter_sector]

        results = []
        progress = st.progress(0)
        status_text = st.empty()

        for i, stock in enumerate(filtered):
            status_text.text(f"Scanning {stock['symbol']} ({i + 1}/{len(filtered)})...")
            progress.progress((i + 1) / len(filtered))
            result = scan_stock(stock["symbol"], sma_period=sma_period)
            if result:
                result["name"] = stock["name"]
                result["sector"] = stock["sector"]
                results.append(result)

        progress.empty()
        status_text.empty()

        if not results:
            st.warning("No data retrieved. Try again.")
            return

        df_results = pd.DataFrame(results)

        if filter_type == "Buy Signals Only":
            df_results = df_results[df_results["buy_signal"] == True]
        elif filter_type == "Above SMA":
            df_results = df_results[df_results["above_sma"] == True]
        elif filter_type == "Breakout":
            df_results = df_results[df_results["breakout"] == True]

        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Stocks Scanned", len(results))
        m2.metric("Buy Signals", int(df_results["buy_signal"].sum()) if len(df_results) > 0 else 0)
        m3.metric("Above SMA", int(df_results["above_sma"].sum()) if len(df_results) > 0 else 0)
        m4.metric("Breakouts", int(df_results["breakout"].sum()) if len(df_results) > 0 else 0)

        st.divider()

        if df_results.empty:
            st.info("No stocks match the filter.")
            return

        df_results = df_results.sort_values(["buy_signal", "vol_ratio"], ascending=[False, False])

        st.dataframe(
            df_results[["symbol", "name", "sector", "close", f"sma", "high_50d", "low_50d", "vol_ratio", "buy_signal", "above_sma", "breakout"]],
            use_container_width=True,
            height=600,
        )

        buy_stocks = df_results[df_results["buy_signal"] == True]
        if not buy_stocks.empty:
            st.divider()
            if nifty["bullish"]:
                st.success(f"{len(buy_stocks)} BUY SIGNAL(S) FOUND! Nifty is BULLISH — good to go!")
            else:
                st.warning(f"{len(buy_stocks)} BUY SIGNAL(S) FOUND! ⚠️ But NIFTY is in DOWNTREND — trade with caution!")

            btn_cols = st.columns(min(5, len(buy_stocks)))
            for j, (_, row) in enumerate(buy_stocks.iterrows()):
                with btn_cols[j % len(btn_cols)]:
                    label = f"{row['symbol']} Rs{row['close']:,.0f}"
                    if st.button(label, key=f"scan_{row['symbol']}", use_container_width=True):
                        st.session_state["selected_stock"] = row["symbol"]
                        st.session_state["page"] = "Charts"
                        st.rerun()

        st.session_state["last_scan"] = df_results.to_dict("records")


def page_portfolio():
    st.markdown(
        "<div class='header-bar'><h1>💼 Portfolio</h1>"
        "<p>Manage positions, track PnL, monitor stop-losses</p></div>",
        unsafe_allow_html=True,
    )

    nifty = check_nifty_bullish()
    st.markdown(get_nifty_warning_html(nifty), unsafe_allow_html=True)

    try:
        capital = st.secrets["trading"]["capital"]
        max_legs = st.secrets["trading"]["max_legs"]
    except Exception:
        capital = 200000
        max_legs = 5

    per_leg = capital * 0.20
    portfolio = st.session_state.get("portfolio", [])
    active = [p for p in portfolio if p.get("status") == "ACTIVE"]

    st.subheader("Add New Position")
    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        add_symbol = st.selectbox("Stock", [s["symbol"] for s in STOCK_LIST], key="add_sym")
    with ac2:
        add_price = st.number_input("Entry Price", min_value=1.0, value=100.0, step=0.5)
    with ac3:
        add_qty = st.number_input("Quantity", min_value=1, value=int(per_leg / max(add_price, 1)))

    if st.button("Add to Portfolio", type="primary"):
        if len(active) >= max_legs:
            st.error(f"Max {max_legs} legs reached!")
        else:
            new_pos = {
                "symbol": add_symbol,
                "entry_date": datetime.now().strftime("%Y-%m-%d"),
                "entry_price": add_price,
                "quantity": add_qty,
                "invested": round(add_price * add_qty, 2),
                "hard_sl": round(add_price * 0.94, 2),
                "trailing_sl": round(add_price * 0.94, 2),
                "active_sl": round(add_price * 0.94, 2),
                "current_price": add_price,
                "current_value": round(add_price * add_qty, 2),
                "pnl": 0,
                "pnl_pct": 0,
                "status": "ACTIVE",
                "days_held": 0,
            }
            st.session_state["portfolio"].append(new_pos)
            st.success(f"Added {add_symbol} @ Rs{add_price}")
            st.rerun()

    st.divider()
    st.subheader(f"Active Positions ({len(active)} / {max_legs})")

    if not active:
        st.info("No active positions.")
    else:
        for pos in active:
            try:
                df_temp = fetch_stock_data(pos["symbol"], period="5d")
                if not df_temp.empty:
                    curr = df_temp["Close"].iloc[-1]
                    pos["current_price"] = round(curr, 2)
                    pos["current_value"] = round(curr * pos["quantity"], 2)
                    pos["pnl"] = round(pos["current_value"] - pos["invested"], 2)
                    pos["pnl_pct"] = round((pos["current_price"] - pos["entry_price"]) / pos["entry_price"] * 100, 2)
                    entry_dt = datetime.strptime(pos["entry_date"], "%Y-%m-%d")
                    pos["days_held"] = (datetime.now() - entry_dt).days
                    df_full = fetch_stock_data(pos["symbol"], period="6mo")
                    if not df_full.empty and len(df_full) >= 50:
                        low_50d = df_full["Low"].rolling(50).min().shift(1).iloc[-1]
                        if not pd.isna(low_50d):
                            new_tsl = max(pos["trailing_sl"], low_50d)
                            pos["trailing_sl"] = round(new_tsl, 2)
                            pos["active_sl"] = round(max(pos["hard_sl"], pos["trailing_sl"]), 2)
            except Exception:
                pass

        df_port = pd.DataFrame(active)
        display_cols = [
            "symbol", "entry_date", "entry_price", "quantity", "invested",
            "hard_sl", "trailing_sl", "active_sl", "current_price",
            "current_value", "pnl", "pnl_pct", "days_held",
        ]
        available_cols = [c for c in display_cols if c in df_port.columns]
        st.dataframe(df_port[available_cols], use_container_width=True)

        st.divider()
        st.subheader("Exit Position")
        exit_symbols = [p["symbol"] for p in active]
        exit_choice = st.selectbox("Select stock to exit", exit_symbols)
        ec1, ec2 = st.columns(2)
        with ec1:
            exit_price = st.number_input("Exit Price", min_value=0.01, value=100.0)
        with ec2:
            exit_reason = st.text_input("Reason", "Manual Exit")

        if st.button("Execute Exit", type="primary"):
            for p in st.session_state["portfolio"]:
                if p["symbol"] == exit_choice and p["status"] == "ACTIVE":
                    p["status"] = "EXITED"
                    exit_val = exit_price * p["quantity"]
                    pnl = exit_val - p["invested"]
                    st.session_state["trade_log"].append({
                        "symbol": exit_choice,
                        "entry_date": p["entry_date"],
                        "entry_price": p["entry_price"],
                        "exit_date": datetime.now().strftime("%Y-%m-%d"),
                        "exit_price": exit_price,
                        "quantity": p["quantity"],
                        "invested": p["invested"],
                        "exit_value": round(exit_val, 2),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round((exit_price - p["entry_price"]) / p["entry_price"] * 100, 2),
                        "days_held": p.get("days_held", 0),
                        "exit_reason": exit_reason,
                    })
                    st.success(f"Exited {exit_choice} @ Rs{exit_price} | PnL: Rs{pnl:,.2f}")
                    break
            st.rerun()


def page_signals():
    st.markdown(
        "<div class='header-bar'><h1>📋 Signals Log</h1>"
        "<p>History of all signals detected</p></div>",
        unsafe_allow_html=True,
    )
    last_scan = st.session_state.get("last_scan", [])
    if last_scan:
        buy_signals = [s for s in last_scan if s.get("buy_signal")]
        if buy_signals:
            st.subheader(f"Buy Signals from Last Scan ({len(buy_signals)})")
            nifty = check_nifty_bullish()
            if not nifty["bullish"]:
                st.warning("⚠️ These signals were generated while NIFTY was in DOWNTREND — trade with caution!")
            st.dataframe(
                pd.DataFrame(buy_signals)[["symbol", "close", "vol_ratio", "high_50d", "low_50d", "sector"]],
                use_container_width=True,
            )
        else:
            st.info("No buy signals in last scan.")
        st.divider()
        st.subheader("All Scanned Stocks")
        st.dataframe(pd.DataFrame(last_scan), use_container_width=True, height=400)
    else:
        st.info("No signals yet. Run the Stock Scanner first.")


def page_tradelog():
    st.markdown(
        "<div class='header-bar'><h1>📜 Trade Log</h1>"
        "<p>Complete history of executed trades</p></div>",
        unsafe_allow_html=True,
    )
    log = st.session_state.get("trade_log", [])
    if not log:
        st.info("No trades recorded yet.")
        return
    df = pd.DataFrame(log)
    total_pnl = df["pnl"].sum()
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] <= 0]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total PnL", f"Rs{total_pnl:,.0f}")
    m2.metric("Winners", len(wins))
    m3.metric("Losers", len(losses))
    m4.metric("Win Rate", f"{len(wins) / len(df) * 100:.0f}%" if len(df) else "N/A")
    st.divider()
    st.dataframe(df, use_container_width=True, height=500)


def page_settings():
    st.markdown(
        "<div class='header-bar'><h1>⚙️ Settings</h1>"
        "<p>Trading system configuration</p></div>",
        unsafe_allow_html=True,
    )
    try:
        capital = st.secrets["trading"]["capital"]
        max_legs = st.secrets["trading"]["max_legs"]
        per_leg = st.secrets["trading"]["per_leg_pct"]
        hard_sl = st.secrets["trading"]["hard_sl_pct"]
        vol_mult = st.secrets["trading"]["volume_multiplier"]
    except Exception:
        capital = 200000
        max_legs = 5
        per_leg = 0.20
        hard_sl = 0.06
        vol_mult = 1.5

    sma_period = st.session_state["sma_period"]

    st.subheader("Current Configuration")
    settings_data = pd.DataFrame({
        "Parameter": [
            "Capital", "Max Legs", "Per Leg %", "Per Leg Amount",
            "Hard SL %", "Volume Multiplier", "SMA Period (selected)",
            "Nifty Filter", "Data Source",
        ],
        "Value": [
            f"Rs{capital:,.0f}", str(max_legs), f"{per_leg * 100:.0f}%",
            f"Rs{capital * per_leg:,.0f}", f"{hard_sl * 100:.0f}%",
            f"{vol_mult}x", f"SMA {sma_period}",
            "SMA 100 (warning mode)", "Yahoo Finance",
        ],
        "Description": [
            "Total trading capital",
            "Max simultaneous positions",
            "% of capital per position",
            "Amount per trade",
            "Fixed stop-loss below entry",
            "Volume threshold for buy signal",
            "Choose 50 or 100 in sidebar",
            "Signals shown always, warning if Nifty bearish",
            "Data provider (Free)",
        ],
    })
    st.table(settings_data)

    st.divider()
    st.subheader("Trading Rules (Your Backtest Logic)")
    st.markdown(f"""
| Rule | Description |
|------|-------------|
| **Box Top** | 50-Day Highest High .shift(1) — excludes today |
| **Trailing SL** | 50-Day Lowest Low .shift(1) — excludes today |
| **BUY** | Close > Box Top AND Close > SMA {sma_period} AND Volume > 1.5x 20D Avg |
| **Hard SL** | 6% below entry price — FIXED, never changes |
| **Trailing SL** | 50D Low — only moves UP, never down |
| **Active SL** | MAX(Hard SL, Trailing SL) |
| **EXIT** | Open <= Active SL (gap down) OR Low <= Active SL (intraday) |
| **Nifty Filter** | Nifty Close > SMA 100 = Bullish. If bearish, signals shown with WARNING |
""")

    st.divider()
    st.subheader("Data Management")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Clear Portfolio", use_container_width=True):
            st.session_state["portfolio"] = []
            st.rerun()
    with c2:
        if st.button("Clear Trade Log", use_container_width=True):
            st.session_state["trade_log"] = []
            st.rerun()
    with c3:
        if st.button("Clear All Data", use_container_width=True):
            st.session_state["portfolio"] = []
            st.session_state["trade_log"] = []
            st.session_state["signals_log"] = []
            st.session_state["last_scan"] = []
            st.rerun()


def main():
    inject_css()
    init_state()
    if not st.session_state["logged_in"]:
        login_page()
        return
    render_sidebar()
    page = st.session_state["page"]
    if page == "Dashboard":
        page_dashboard()
    elif page == "Charts":
        page_charts()
    elif page == "Stock Scanner":
        page_scanner()
    elif page == "Portfolio":
        page_portfolio()
    elif page == "Signals Log":
        page_signals()
    elif page == "Trade Log":
        page_tradelog()
    elif page == "Settings":
        page_settings()


if __name__ == "__main__":
    main()
