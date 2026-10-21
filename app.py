import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Today's Trade Setup & 7-Day Analyzer", layout="wide")
st.title("📊 Today's Trade Signal & Candle Analyzer")

# Sidebar Controls
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "AAPL")
risk_percent = st.sidebar.slider("Stop Loss Risk %", min_value=1.0, max_value=5.0, value=2.0, step=0.5)

def analyze_7day_patterns(df):
    """Analyzes the last 7 days of price action for candlestick patterns."""
    patterns = []
    if len(df) < 2:
        return patterns

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    curr_open, curr_close = float(curr['Open']), float(curr['Close'])
    curr_high, curr_low = float(curr['High']), float(curr['Low'])
    prev_open, prev_close = float(prev['Open']), float(prev['Close'])

    body_size = abs(curr_close - curr_open)
    total_range = curr_high - curr_low
    lower_wick = min(curr_open, curr_close) - curr_low
    upper_wick = curr_high - max(curr_open, curr_close)

    # 1. Bullish Engulfing
    if prev_close < prev_open and curr_close > curr_open and curr_close >= prev_open:
        patterns.append(("BULLISH", "Bullish Engulfing Pattern"))
    # 2. Bearish Engulfing
    if prev_close > prev_open and curr_close < curr_open and curr_close <= prev_open:
        patterns.append(("BEARISH", "Bearish Engulfing Pattern"))
    # 3. Hammer Reversal
    if total_range > 0 and (lower_wick >= 2 * body_size) and (upper_wick <= 0.2 * body_size) and curr_close > curr_open:
        patterns.append(("BULLISH", "Hammer Reversal Pattern"))
    # 4. Shooting Star
    if total_range > 0 and (upper_wick >= 2 * body_size) and (lower_wick <= 0.2 * body_size) and curr_close < curr_open:
        patterns.append(("BEARISH", "Shooting Star Pattern"))
    # 5. Doji Indecision
    if total_range > 0 and (body_size / total_range) < 0.1:
        patterns.append(("NEUTRAL", "Doji (Indecision Candle)"))

    return patterns

if ticker:
    # Fetch data for technical indicators and 7-day analysis
    data = yf.download(ticker, period="30d", interval="1d")
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # 1. Calculate 7-Day Indicators
        data['SMA5'] = data['Close'].rolling(5).mean()
        data['SMA20'] = data['Close'].rolling(20).mean()

        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))

        # Extract last 7 days for context & today's row
        last_7_days = data.tail(7)
        today = data.iloc[-1]
        prev = data.iloc[-2]

        today_price = float(today['Close'])
        today_open = float(today['Open'])
        today_high = float(today['High'])
        today_low = float(today['Low'])

        # 2. Evaluate Today's Signal based on 7-Day Context
        patterns = analyze_7day_patterns(last_7_days)
        bullish_score, bearish_score = 0, 0
        reasons = []

        # Moving Average Crossover
        if prev['SMA5'] <= prev['SMA20'] and today['SMA5'] > today['SMA20']:
            bullish_score += 2
            reasons.append("Golden Cross (5-SMA crossed above 20-SMA)")
        elif prev['SMA5'] >= prev['SMA20'] and today['SMA5'] < today['SMA20']:
            bearish_score += 2
            reasons.append("Death Cross (5-SMA crossed below 20-SMA)")

        # RSI Checks
        if today['RSI'] < 35:
            bullish_score += 1
            reasons.append(f"Oversold RSI ({today['RSI']:.1f})")
        elif today['RSI'] > 65:
            bearish_score += 1
            reasons.append(f"Overbought RSI ({today['RSI']:.1f})")

        # Today's Price Movement relative to 7-Day High/Low
        if today_price > last_7_days['High'].iloc[:-1].max():
            bullish_score += 1
            reasons.append("Breakout: Today's price broke above the 7-day high.")
        elif today_price < last_7_days['Low'].iloc[:-1].min():
            bearish_score += 1
            reasons.append("Breakdown: Today's price dropped below the 7-day low.")

        # Add Candle Patterns
        for bias, p_name in patterns:
            if bias == "BULLISH":
                bullish_score += 1
                reasons.append(f"Pattern: {p_name}")
            elif bias == "BEARISH":
                bearish_score += 1
                reasons.append(f"Pattern: {p_name}")

        # Signal Verdict
        if bullish_score > bearish_score and bullish_score >= 2:
            signal = "BUY"
        elif bearish_score > bullish_score and bearish_score >= 2:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        # 3. Display Dashboard Header
        st.subheader(f"Today's Signal Dashboard: {ticker.upper()}")

        if signal == "BUY":
            st.success("🟢 TODAY'S ACTION: BUY / LONG SETUP")
        elif signal == "SELL":
            st.error("🔴 TODAY'S ACTION: SELL / SHORT SETUP")
        else:
            st.info("🟡 TODAY'S ACTION: NEUTRAL / HOLD — No high-probability setup today.")

        # 4. Show Today's Specific Buy/Sell Setup Values
        if signal in ["BUY", "SELL"]:
            risk_amount = today_price * (risk_percent / 100.0)

            if signal == "BUY":
                entry_price = today_price
                stop_loss = entry_price - risk_amount
                target_1 = entry_price + (risk_amount * 1.5)
                target_2 = entry_price + (risk_amount * 3.0)
            else:  # SELL
                entry_price = today_price
                stop_loss = entry_price + risk_amount
                target_1 = entry_price - (risk_amount * 1.5)
                target_2 = entry_price - (risk_amount * 3.0)

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Today's Entry", f"${entry_price:.2f}")
            col2.metric("Stop Loss", f"${stop_loss:.2f}", delta=f"-{risk_percent}%" if signal == "BUY" else f"+{risk_percent}%")
            col3.metric("Target 1", f"${target_1:.2f}", delta="1:1.5 R/R")
            col4.metric("Target 2", f"${target_2:.2f}", delta="1:3.0 R/R")
            col5.metric("RSI (14-Day)", f"{today['RSI']:.1f}")

        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Today's Close", f"${today_price:.2f}")
            col2.metric("RSI (14-Day)", f"{today['RSI']:.1f}")
            col3.metric("Status", "Awaiting Setup")

        st.markdown("**Today's Analysis Rationale:**")
        for r in reasons:
            st.write(f"- {r}")
        if not reasons:
            st.write("- Market consolidating over the last 7 days. No clear setup today.")

        # 5. Render Chart ONLY for Today's Candle
        today_df = data.tail(1)

        fig = go.Figure()

        # Single Candlestick for Today
        fig.add_trace(go.Candlestick(
            x=today_df.index,
            open=today_df['Open'],
            high=today_df['High'],
            low=today_df['Low'],
            close=today_df['Close'],
            name="Today's Candle"
        ))

        # Add Target Lines ONLY if Signal is BUY or SELL
        if signal in ["BUY", "SELL"]:
            fig.add_hline(y=target_2, line_dash="dash", line_color="green", annotation_text=f"Target 2 (${target_2:.2f})", annotation_position="top right")
            fig.add_hline(y=target_1, line_dash="dash", line_color="lightgreen", annotation_text=f"Target 1 (${target_1:.2f})", annotation_position="top right")
            fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", annotation_text=f"Stop Loss (${stop_loss:.2f})", annotation_position="bottom right")

        fig.update_layout(
            title=f"Today's Price Candle for {ticker.upper()}",
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            height=450
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Could not fetch data for this ticker.")
