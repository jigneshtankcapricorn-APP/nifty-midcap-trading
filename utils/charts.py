"""
Chart — Lines only, no box rectangles
Matches backtest logic exactly
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import timedelta


def create_darvas_chart(
    df: pd.DataFrame,
    symbol: str,
    show_signals: bool = True,
    show_bands: bool = True,
    sma_period: int = 50,
    nifty_bullish: bool = True,
    chart_height: int = 800,
) -> go.Figure:

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.72, 0.28],
    )

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

    if "SMA" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA"],
                name=f"SMA {sma_period}",
                line=dict(color="#42A5F5", width=2),
                opacity=0.85,
            ),
            row=1, col=1,
        )

    if show_bands and "Box_Top" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Box_Top"],
                name="50D High (Breakout Level)",
                line=dict(color="#FF9800", width=2, dash="dash"),
                opacity=0.7,
            ),
            row=1, col=1,
        )

    if show_bands and "Trailing_SL" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Trailing_SL"],
                name="50D Low (Trailing SL)",
                line=dict(color="#AB47BC", width=2, dash="dash"),
                opacity=0.7,
                fill="tonexty" if show_bands and "Box_Top" in df.columns else None,
                fillcolor="rgba(255,152,0,0.04)",
            ),
            row=1, col=1,
        )

    if show_signals and "Buy_Signal" in df.columns:
        buys = df[df["Buy_Signal"]]
        if not buys.empty:
            buy_color = "#00E676" if nifty_bullish else "#FFD600"
            buy_label = "BUY" if nifty_bullish else "BUY*"

            fig.add_trace(
                go.Scatter(
                    x=buys.index,
                    y=buys["Low"] * 0.97,
                    mode="markers+text",
                    name=f"BUY {'(Nifty OK)' if nifty_bullish else '(Nifty DOWN)'}",
                    text=[buy_label] * len(buys),
                    textposition="bottom center",
                    textfont=dict(size=10, color=buy_color),
                    marker=dict(
                        symbol="triangle-up",
                        size=16,
                        color=buy_color,
                        line=dict(color=buy_color, width=1),
                    ),
                ),
                row=1, col=1,
            )

            for idx_date, row in buys.iterrows():
                sl = row["Close"] * 0.94
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
                    text=f"SL Rs{sl:.0f} (-6%)",
                    showarrow=False,
                    font=dict(size=8, color="#FF1744"),
                    xanchor="left",
                    yshift=-10,
                    row=1, col=1,
                )

    if show_signals and "Sell_Signal" in df.columns:
        sells = df[df["Sell_Signal"]]
        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=sells.index,
                    y=sells["High"] * 1.02,
                    mode="markers+text",
                    name="EXIT (Low hit SL)",
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

    if "Vol_SMA_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Vol_SMA_20"],
                name="20D Avg Vol",
                line=dict(color="#FFC107", width=1.5),
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Vol_SMA_20"] * 1.5,
                name="1.5x Vol Threshold",
                line=dict(color="#FF5252", width=1, dash="dash"),
                opacity=0.5,
            ),
            row=2, col=1,
        )

    nifty_tag = "" if nifty_bullish else " | Nifty Downtrend"
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol}</b> SMA {sma_period} | 50D Breakout{nifty_tag}",
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
    fig.update_yaxes(title_text="Price (Rs)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig
