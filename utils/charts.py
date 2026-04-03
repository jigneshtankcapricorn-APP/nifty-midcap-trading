"""
Professional Darvas Box chart with Plotly.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import timedelta


def create_darvas_chart(
    df: pd.DataFrame,
    symbol: str,
    boxes: list | None = None,
    show_signals: bool = True,
    show_darvas_bands: bool = True,
    show_traditional_boxes: bool = True,
    chart_height: int = 800,
) -> go.Figure:
    """
    Create a professional candlestick chart with Darvas Box overlays.
    
    Features
    --------
    - Candlestick chart
    - 50-Day High / Low bands  (modified Darvas)
    - Traditional Darvas Box rectangles
    - SMA-50 line
    - Buy-signal markers   (▲ green)
    - SL-level markers      (▼ red / dashed lines)
    - Volume bars  (coloured) + 20-day avg + 1.5× threshold
    """

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.72, 0.28],
        subplot_titles=[None, None],
    )

    # ═══════════════ 1.  CANDLESTICKS ═══════════════
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price",
            increasing_line_color="#26A69A",
            increasing_fillcolor="#26A69A",
            decreasing_line_color="#EF5350",
            decreasing_fillcolor="#EF5350",
            line_width=1,
        ),
        row=1, col=1,
    )

    # ═══════════════ 2.  SMA-50 ═══════════════
    if "SMA50" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["SMA50"], name="SMA 50",
                line=dict(color="#42A5F5", width=2),
                opacity=0.85,
            ),
            row=1, col=1,
        )

    # ═══════════════ 3.  DARVAS BANDS (50D Hi / Lo) ═══════════════
    if show_darvas_bands and "High_50D" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["High_50D"], name="50D High (Box Top)",
                line=dict(color="#FF9800", width=1.5, dash="dash"),
                opacity=0.7,
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["Low_50D"], name="50D Low (Box Bottom)",
                line=dict(color="#AB47BC", width=1.5, dash="dash"),
                opacity=0.7,
                fill="tonexty",
                fillcolor="rgba(171,71,188,0.06)",
            ),
            row=1, col=1,
        )

    # ═══════════════ 4.  TRADITIONAL DARVAS BOXES ═══════════════
    if show_traditional_boxes and boxes:
        for bx in boxes:
            border = "#00E676" if bx["breakout"] else (
                "#FF1744" if bx["breakout"] is False else "#FFC107"
            )
            fill = "rgba(0,230,118,0.08)" if bx["breakout"] else (
                "rgba(255,23,68,0.08)" if bx["breakout"] is False
                else "rgba(255,193,7,0.08)"
            )
            fig.add_shape(
                type="rect",
                x0=bx["start"], x1=bx["end"],
                y0=bx["bottom"], y1=bx["top"],
                line=dict(color=border, width=1.5),
                fillcolor=fill,
                row=1, col=1,
            )

    # ═══════════════ 5.  BUY SIGNALS ═══════════════
    if show_signals and "Buy_Signal" in df.columns:
        buys = df[df["Buy_Signal"]]
        if not buys.empty:
            fig.add_trace(
                go.Scatter(
                    x=buys.index,
                    y=buys["Low"] * 0.97,
                    mode="markers+text",
                    name="🟢 BUY Signal",
                    text=["BUY"] * len(buys),
                    textposition="bottom center",
                    textfont=dict(size=9, color="#00E676"),
                    marker=dict(
                        symbol="triangle-up", size=14,
                        color="#00E676",
                        line=dict(color="#00C853", width=1),
                    ),
                ),
                row=1, col=1,
            )
            # SL lines for each buy
            for idx, row in buys.iterrows():
                sl = row["Close"] * 0.94
                end_date = idx + timedelta(days=40)
                fig.add_shape(
                    type="line",
                    x0=idx, x1=end_date,
                    y0=sl, y1=sl,
                    line=dict(color="#FF1744", width=1, dash="dot"),
                    row=1, col=1,
                )
                fig.add_annotation(
                    x=idx, y=sl,
                    text=f"SL ₹{sl:.0f}",
                    showarrow=False,
                    font=dict(size=8, color="#FF1744"),
                    xanchor="left",
                    row=1, col=1,
                )

    # ═══════════════ 6.  SELL SIGNALS ═══════════════
    if show_signals and "Sell_Signal" in df.columns:
        sells = df[df["Sell_Signal"]]
        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=sells.index,
                    y=sells["High"] * 1.02,
                    mode="markers+text",
                    name="🔴 EXIT Signal",
                    text=["EXIT"] * len(sells),
                    textposition="top center",
                    textfont=dict(size=9, color="#FF1744"),
                    marker=dict(
                        symbol="triangle-down", size=14,
                        color="#FF1744",
                        line=dict(color="#D50000", width=1),
                    ),
                ),
                row=1, col=1,
            )

    # ═══════════════ 7.  VOLUME BARS ═══════════════
    vol_colors = [
        "#26A69A" if c >= o else "#EF5350"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df.index, y=df["Volume"], name="Volume",
            marker_color=vol_colors, opacity=0.65,
            showlegend=False,
        ),
        row=2, col=1,
    )

    if "Avg_Vol_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["Avg_Vol_20"],
                name="20D Avg Vol",
                line=dict(color="#FFC107", width=1.5),
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["Avg_Vol_20"] * 1.5,
                name="1.5× Vol Threshold",
                line=dict(color="#FF5252", width=1, dash="dash"),
                opacity=0.6,
            ),
            row=2, col=1,
        )

    # ═══════════════ 8.  LAYOUT ═══════════════
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol}</b>  —  Darvas Box Analysis",
            font=dict(size=18, color="#E0E0E0"),
            x=0.01,
        ),
        height=chart_height,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=10),
            bgcolor="rgba(0,0,0,0.4)",
        ),
        margin=dict(l=60, r=20, t=60, b=30),
        hovermode="x unified",
    )

    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])],
        gridcolor="rgba(128,128,128,0.15)",
        showgrid=True,
    )
    fig.update_yaxes(
        gridcolor="rgba(128,128,128,0.15)",
        showgrid=True,
    )
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


# ───────── Small sparkline chart for scanner ─────────
def create_mini_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    """Compact sparkline for the scanner page."""
    if df.empty:
        return go.Figure()

    last_30 = df.tail(30)
    color = "#26A69A" if last_30["Close"].iloc[-1] >= last_30["Close"].iloc[0] else "#EF5350"

    fig = go.Figure(
        go.Scatter(
            x=last_30.index, y=last_30["Close"],
            mode="lines", fill="tozeroy",
            line=dict(color=color, width=1.5),
            fillcolor=color.replace(")", ",0.1)").replace("rgb", "rgba"),
        )
    )
    fig.update_layout(
        height=80, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig
