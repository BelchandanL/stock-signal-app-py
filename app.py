import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Intraday Trade Setup & Live Candle Analyzer", layout="wide")
st.title("⚡ Today's Intraday Live Trade Setup & Signal Dashboard")

# Sidebar Controls
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "AAPL")
interval_choice = st.sidebar.selectbox("Intraday Timeframe", ["5m", "15m", "30m", "1h"], index=0)
risk_percent = st.sidebar.slider("Stop Loss Risk %", min_value=0.5, max_value=3.0, value=1.0, step=0.25)

def analyze_intraday_patterns(df):
    """Detects candlestick price action patterns on recent intraday bars."""
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

    return patterns

if ticker:
    try:
        # Fetch Intraday Data for Today (5-minute interval bars)
        data = yf.download(ticker.strip().upper(), period="5d", interval=interval_choice)
        
        if not data.empty:
            # Flatten MultiIndex columns if present
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # 1. Calculate Intraday Technical Indicators
            data['SMA5'] = data['Close'].rolling(5).mean()
            data['SMA20'] = data['Close'].rolling(20).mean()

            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            data['RSI'] = 100 - (100 / (1 + rs))

            # Clean rows with NaN indicators
            clean_data = data.dropna(subset=['SMA5', 'SMA20', 'RSI']).copy()

            # Filter strictly for Today's Intraday Session
            latest_date = clean_data.index[-1].date()
            today_candles = clean_data[clean_data.index.date == latest_date].copy()

            if today_candles.empty or len(today_candles) < 2:
                # Fallback to last available session if market is currently closed
                today_candles = clean_data.tail(30).copy()

            latest_bar = today_candles.iloc[-1]
            prev_bar = today_candles.iloc[-2]
            current_price = float(latest_bar['Close'])

            # 2. Evaluate Intraday Signal
            patterns = analyze_intraday_patterns(today_candles)
            bullish_score, bearish_score = 0, 0
            reasons = []

            # Moving Average Crossover
            if float(prev_bar['SMA5']) <= float(prev_bar['SMA20']) and float(latest_bar['SMA5']) > float(latest_bar['SMA20']):
                bullish_score += 2
                reasons.append("Intraday Golden Cross: 5-SMA crossed above 20-SMA")
            elif float(prev_bar['SMA5']) >= float(prev_bar['SMA20']) and float(latest_bar['SMA5']) < float(latest_bar['SMA20']):
                bearish_score += 2
                reasons.append("Intraday Death Cross: 5-SMA crossed below 20-SMA")

            # Momentum relative to SMA
            if float(latest_bar['SMA5']) > float(latest_bar['SMA20']):
                bullish_score += 1
                reasons.append("Short-term momentum is Bullish (5-SMA > 20-SMA)")
            elif float(latest_bar['SMA5']) < float(latest_bar['SMA20']):
                bearish_score += 1
                reasons.append("Short-term momentum is Bearish (5-SMA < 20-SMA)")

            # RSI Check
            rsi_val = float(latest_bar['RSI'])
            if rsi_val < 35:
                bullish_score += 1
                reasons.append(f"Oversold RSI ({rsi_val:.1f})")
            elif rsi_val > 65:
                bearish_score += 1
                reasons.append(f"Overbought RSI ({rsi_val:.1f})")

            # Candlestick Patterns
            for bias, p_name in patterns:
                if bias == "BULLISH":
                    bullish_score += 1
                    reasons.append(f"Pattern: {p_name}")
                elif bias == "BEARISH":
                    bearish_score += 1
                    reasons.append(f"Pattern: {p_name}")

            # Signal Verdict (Force Active Setup if momentum favors one direction)
            if bullish_score > bearish_score:
                signal = "BUY"
            elif bearish_score > bullish_score:
                signal = "SELL"
            else:
                signal = "NEUTRAL"

            # 3. Header Banner
            st.subheader(f"Today's Live Intraday Dashboard: {ticker.upper()} ({interval_choice} Bars)")

            if signal == "BUY":
                st.success("🟢 RECOMMENDED ACTION: BUY / LONG SETUP")
            elif signal == "SELL":
                st.error("🔴 RECOMMENDED ACTION: SELL / SHORT SETUP")
            else:
                st.info("🟡 RECOMMENDED ACTION: NEUTRAL / HOLD — Awaiting clear breakout.")

            # 4. Display Entry, Stop Loss, and Targets (Always calculated for active setup)
            risk_amount = current_price * (risk_percent / 100.0)

            if signal == "BUY":
                entry_price = current_price
                stop_loss = entry_price - risk_amount
                target_1 = entry_price + (risk_amount * 1.5)
                target_2 = entry_price + (risk_amount * 3.0)
            elif signal == "SELL":
                entry_price = current_price
                stop_loss = entry_price + risk_amount
                target_1 = entry_price - (risk_amount * 1.5)
                target_2 = entry_price - (risk_amount * 3.0)
            else:  # Fallback Default Buy Setup
                entry_price = current_price
                stop_loss = entry_price - risk_amount
                target_1 = entry_price + (risk_amount * 1.5)
                target_2 = entry_price + (risk_amount * 3.0)

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Current Entry", f"${entry_price:.2f}")
            col2.metric("Stop Loss", f"${stop_loss:.2f}", delta=f"-{risk_percent}%" if signal != "SELL" else f"+{risk_percent}%")
            col3.metric("Target 1", f"${target_1:.2f}", delta="1:1.5 R/R")
            col4.metric("Target 2", f"${target_2:.2f}", delta="1:3.0 R/R")
            col5.metric("RSI (Intraday)", f"{rsi_val:.1f}")

            st.markdown("**Intraday Signal Rationale:**")
            for r in reasons:
                st.write(f"- {r}")

            # 5. Render Chart showing ALL Ongoing Trade Candles for Today Only
            fig = go.Figure()

            # Plot today's intraday candle series
            fig.add_trace(go.Candlestick(
                x=today_candles.index,
                open=[float(x) for x in today_candles['Open']],
                high=[float(x) for x in today_candles['High']],
                low=[float(x) for x in today_candles['Low']],
                close=[float(x) for x in today_candles['Close']],
                name="Intraday Candles"
            ))

            # Add Moving Averages
            fig.add_trace(go.Scatter(x=today_candles.index, y=today_candles['SMA5'], line=dict(color='blue', width=1.5), name='5-SMA'))
            fig.add_trace(go.Scatter(x=today_candles.index, y=today_candles['SMA20'], line=dict(color='orange', width=1.5), name='20-SMA'))

            # Horizontal Lines for Entry, Stop Loss, Target 1, Target 2
            fig.add_hline(y=target_2, line_dash="dash", line_color="green", annotation_text=f"Target 2 (${target_2:.2f})", annotation_position="top right")
            fig.add_hline(y=target_1, line_dash="dash", line_color="lightgreen", annotation_text=f"Target 1 (${target_1:.2f})", annotation_position="top right")
            fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", annotation_text=f"Stop Loss (${stop_loss:.2f})", annotation_position="bottom right")

            fig.update_layout(
                title=f"Today's Ongoing Intraday Candles ({interval_choice}) for {ticker.upper()}",
                xaxis_rangeslider_visible=False,
                template="plotly_white",
                height=550
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.error("Could not fetch intraday data for this ticker.")

    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
