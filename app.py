import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(page_title="7-Day Stock & Projection Signal Analyzer", layout="wide")
st.title("📈 7-Day Stock Analyzer with Predictive Projection & Signals")

# Sidebar Controls
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "AAPL")
risk_percent = st.sidebar.slider("Stop Loss Risk %", min_value=1.0, max_value=5.0, value=2.0, step=0.5)

def detect_7day_patterns(df):
    """Analyzes recent 7-day candlestick movement for signals."""
    patterns = []
    if len(df) < 7:
        return patterns

    recent = df.tail(7)
    curr = recent.iloc[-1]
    prev = recent.iloc[-2]

    curr_open, curr_close = float(curr['Open']), float(curr['Close'])
    curr_high, curr_low = float(curr['High']), float(curr['Low'])
    prev_open, prev_close = float(prev['Open']), float(prev['Close'])

    body_size = abs(curr_close - curr_open)
    total_range = curr_high - curr_low
    lower_wick = min(curr_open, curr_close) - curr_low
    upper_wick = curr_high - max(curr_open, curr_close)

    # Patterns
    if prev_close < prev_open and curr_close > curr_open and curr_close >= prev_open:
        patterns.append(("BULLISH", "Bullish Engulfing within 7-day window"))
    if prev_close > prev_open and curr_close < curr_open and curr_close <= prev_open:
        patterns.append(("BEARISH", "Bearish Engulfing within 7-day window"))
    if total_range > 0 and (lower_wick >= 2 * body_size) and (upper_wick <= 0.2 * body_size) and curr_close > curr_open:
        patterns.append(("BULLISH", "Hammer Reversal Pattern"))
    if total_range > 0 and (upper_wick >= 2 * body_size) and (lower_wick <= 0.2 * body_size) and curr_close < curr_open:
        patterns.append(("BEARISH", "Shooting Star Pattern"))
        
    # Check 7-day higher highs/lows momentum
    highs = recent['High'].values
    lows = recent['Low'].values
    if highs[-1] > highs[-3] and lows[-1] > lows[-3]:
        patterns.append(("BULLISH", "7-Day Uptrend (Higher Highs & Higher Lows)"))
    elif highs[-1] < highs[-3] and lows[-1] < lows[-3]:
        patterns.append(("BEARISH", "7-Day Downtrend (Lower Highs & Lower Lows)"))

    return patterns

def generate_future_candles(last_row, signal_type, days=5):
    """Generates dummy future candles based on current trend bias."""
    future_data = []
    last_date = last_row.name
    last_close = float(last_row['Close'])

    daily_volatility = last_close * 0.015  # ~1.5% daily variation
    bias_drift = 0.008 if signal_type == "BUY" else (-0.008 if signal_type == "SELL" else 0.001)

    curr_p = last_close
    for i in range(1, days + 1):
        future_date = last_date + timedelta(days=i if last_date.weekday() < 4 else i + 2)
        drift = curr_p * bias_drift
        open_p = curr_p
        close_p = open_p + drift + np.random.normal(0, daily_volatility * 0.4)
        high_p = max(open_p, close_p) + abs(np.random.normal(0, daily_volatility * 0.3))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, daily_volatility * 0.3))
        
        future_data.append({
            'Date': future_date,
            'Open': open_p,
            'High': high_p,
            'Low': low_p,
            'Close': close_p
        })
        curr_p = close_p

    df_fut = pd.DataFrame(future_data)
    df_fut.set_index('Date', inplace=True)
    return df_fut

if ticker:
    # Fetch 200 days for long-term indicators (SMA 50/20
