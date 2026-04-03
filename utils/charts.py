"""
Chart visualization matching App Script Darvas Box logic
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import timedelta


def create_darvas_chart(
    df: pd.DataFrame,
    symbol: str,
    boxes: list = None,
    show_signals: bool = True,
    show_darvas_bands: bool = True,
    show_traditional_boxes: bool = True,
    chart_height: int = 800,
) -> go.Figure:
    """
    Chart matching YOUR App Script logic:
    - 50D High = orange dashed line (breakout level / box ceiling)
    - 50D Low  = purple dashed line (trailing SL / box floor)
    - Zone between them = the Darvas box zone
    - Green ▲ = BUY signal (all 3 conditions met)
    - Red ▼ = EXIT signal (close < 50D Low)
    - Red dotted line = Hard SL (6% below entry)
    """
    if boxes is None:
        boxes = []

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.72, 0.28],
    )

    # ══════ 1. CANDLESTICKS ══════
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            increasing_line_color="#26A69A",
            increasing_fillcolor="#26A69A",
            decreasing_line_color="#EF5350",
            decreasing_fillcolor="#EF5350",
            line_width=1,
        ),
        row=1, col=1,
    )

    # ══════ 2. SMA 50 ══════
    if "SMA50" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA50"],
                name="SMA 50 (trend filter)",
                line=dict(color="#42A5F5", width=2),
                opacity=0.85,
            ),
            row=1, col=1,
        )

    # ══════ 3. 50D HIGH & LOW BANDS (YOUR APP SCRIPT LEVELS) ══════
    if show_darvas_bands:
        if "High_50D" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["High_50D"],
                    name="50D High (breakout ceiling)",
                    line=dict(color="#FF9800", width=2, dash="dash"),
                    opacity=0.7,
                ),
                row=1, col=1,
            )

        if "Low_50D" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["Low_50D"],
                    name="50D Low (trailing SL floor)",
                    line=dict(color="#AB47BC", width=2, dash="dash"),
                    opacity=0.7,
                    fill="tonexty",
                    fillcolor="rgba(255,152,0,0.05)",
                ),
                row=1, col=1,
            )

    # ══════ 4. DARVAS BOX RECTANGLES ══════
    if show_traditional_boxes and boxes:
        for bx in boxes:
            if bx["breakout"] is True:
                border = "#00E676"
                fill = "rgba(0,230,118,0.10)"
                label_text = f"▲ BREAKOUT ₹{bx.get('breakout_price', bx['top']):.0f}"
            elif bx["breakout"] is False:
                border = "#FF1744"
                fill = "rgba(255,23,68,0.10)"
                label_text = f"▼ BREAKDOWN ₹{bx.get('breakout_price', bx['bottom']):.0f}"
            else:
                border = "#FFC107"
                fill = "rgba(255,193,7,0.08)"
                label_text = "⏳ ACTIVE BOX"

            # Draw box rectangle
            fig.add_shape(
                type="rect",
                x0=bx["start"],
                x1=bx["end"],
                y0=bx["bottom"],
                y1=bx["top"],
                line=dict(color=border, width=2),
                fillcolor=fill,
                row=1, col=1,
            )

            # Top price label
            mid_time = bx["start"] + (bx["end"] - bx["start"]) / 2
            fig.add_annotation(
                x=mid_time,
                y=bx["top"],
                text=f"₹{bx['top']:.0f}",
                showarrow=False,
                font=dict(size=9, color=border),
                yshift=14,
                row=1, col=1,
            )

            # Bottom price label
            fig.add_annotation(
                x=mid_time,
                y=bx["bottom"],
                text=f"₹{bx['bottom']:.0f}",
                showarrow=False,
                font=dict(size=8, color="#888"),
                yshift=-14,
                row=1, col=1,
            )

            # Box info label
            candles = bx.get("candles", 0)
            height = bx.get("height_pct", 0)
            mid_price = (bx["top"] + bx["bottom"]) / 2
            fig.add_annotation(
                x=mid_time,
                y=mid_price,
                text=f"{candles}d | {height:.1f}%",
                showarrow=False,
                font=dict(size=8, color="#aaa"),
                opacity=0.7,
                row=1, col=1,
            )

    # ══════ 5. BUY SIGNALS (YOUR APP SCRIPT: breakout + SMA + volume) ══════
    if show_signals and "Buy_Signal" in df.columns:
        buys = df[df["Buy_Signal"]]
        if not buys.empty:
            fig.add_trace(
                go.Scatter(
                    x=buys.index,
                    y=buys["Low"] * 0.97,
                    mode="markers+text",
                    name="BUY (breakout+SMA+vol)",
                    text=["BUY"] * len(buys),
                    textposition="bottom center",
                    textfont=dict(size=10, color="#00E676"),
                    marker=dict(
                        symbol="triangle-up",
                        size=16,
                        color="#00E676",
                        line=dict(color="#00C853", width=1),
                    ),
                ),
                row=1, col=1,
            )

            # Hard SL line for each buy (6% below entry — YOUR APP SCRIPT)
            for idx_date, row in buys.iterrows():
                sl = row["Close"] * 0.94  # hardSL = close * (1 - 0.06)
                end_date = idx_date + timedelta(days=40)

                fig.add_shape(
                    type="line",
                    x0=idx_date,
                    x1=end_date,
                    y0=sl,
                    y1=sl,
                    line=dict(color="#FF1744", width=1.5, dash="dot"),
                    row=1, col=1,
                )
                fig.add_annotation(
                    x=idx_date,
                    y=sl,
                    text=f"Hard SL ₹{sl:.0f} (-6%)",
                    showarrow=False,
                    font=dict(size=8, color="#FF1744"),
                    xanchor="left",
                    yshift=-10,
                    row=1, col=1,
                )

    # ══════ 6. EXIT SIGNALS (Close < 50D Low) ══════
    if show_signals and "Sell_Signal" in df.columns:
        sells = df[df["Sell_Signal"]]
        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=sells.index,
                    y=sells["High"] * 1.02,
                    mode="markers+text",
                    name="EXIT (below 50D Low)",
                    text=["EXIT"] * len(sells),
                    textposition="top center",
                    textfont=dict(size=9, color="#FF1744"),
                    marker=dict(
                        symbol="triangle-down",
                        size=14,
                        color="#FF1744",
                        line=dict(color="#D50000", width=1),
                    ),
                ),
                row=1, col=1,
            )

    # ══════ 7. VOLUME BARS ══════
    vol_colors = [
        "#26A69A" if c >= o else "#EF5350"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Volume",
            marker_color=vol_colors,
            opacity=0.65,
            showlegend=False,
        ),
        row=2, col=1,
    )

    # 20D Avg Volume line
    if "Avg_Vol_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Avg_Vol_20"],
                name="20D Avg Vol",
                line=dict(color="#FFC107", width=1.5),
            ),
            row=2, col=1,
        )
        # 1.5x threshold (YOUR APP SCRIPT condition)
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Avg_Vol_20"] * 1.5,
                name="1.5× Vol (buy threshold)",
                line=dict(color="#FF5252", width=1, dash="dash"),
                opacity=0.5,
            ),
            row=2, col=1,
        )

    # ══════ 8. LAYOUT ══════
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol}</b> — Darvas Box Analysis (App Script Logic)",
            font=dict(size=18, color="#E0E0E0"),
            x=0.01,
        ),
        height=chart_height,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
            bgcolor="rgba(0,0,0,0.4)",
        ),
        margin=dict(l=60, r=20, t=60, b=30),
        hovermode="x unified",
    )

    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])],
        gridcolor="rgba(128,128,128,0.15)",
    )
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig
