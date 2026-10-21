import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(page_title="Today's Trade Setup & 3-Day Forecast", layout="wide")
st.title("📊 Today's Trade Signal & 3-Day Projection Analyzer")

# Sidebar Controls
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "AAPL")
risk_percent = st.sidebar.slider("Stop Loss Risk %", min_value=1.0, max_value=5.0, value=2.0, step=0.5)

def analyze_7day_patterns(df):
    """Analyzes recent candles for price action patterns."""
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

def generate_3day_forecast(last_row, signal_type, recent_df):
    """Generates 3 hypothetical future candles based on trend momentum and volatility."""
    future_candles = []
    last_date = last_row.name
    last_close = float(last_row['Close'])

    # Average daily volatility range from recent data
    recent_ranges = (recent_df['High'] - recent_df['Low']) / recent_df['Close']
    avg_volatility = float(recent_ranges.mean()) if not recent_ranges.empty else 0.015

    # Directional drift factor
    if signal_type == "BUY":
        drift_pct = 0.008
    elif signal_type == "SELL":
        drift_pct = -0.008
    else:
        drift_pct = 0.001

    curr_p = last_close
    curr_date = last_date

    for _ in range(3):
        # Advance to next weekday
        curr_date += timedelta(days=1)
        while curr_date.weekday() >= 5:
            curr_date += timedelta(days=1)

        expected_move = curr_p * drift_pct
        open_p = curr_p
        close_p = open_p + expected_move + np.random.normal(0, curr_p * avg_volatility * 0.3)
        high_p = max(open_p, close_p) + abs(np.random.normal(0, curr_p * avg_volatility * 0.25))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, curr_p * avg_volatility * 0.25))

        future_candles.append({
            'Date': curr_date,
            'Open': float(open_p),
            'High': float(high_p),
            'Low': float(low_p),
            'Close': float(close_p)
        })
        curr_p = close_p

    df_fut = pd.DataFrame(future_candles)
    df_fut.set_index('Date', inplace=True)
    return df_fut

if ticker:
    try:
        # Fetch data for 60 days to allow SMA warmup
        data = yf.download(ticker.strip().upper(), period="60d", interval="1d")
        
        if not data.empty:
            # Flatten MultiIndex columns if present
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # 1. Technical Indicators Calculation
            data['SMA5'] = data['Close'].rolling(5).mean()
            data['SMA20'] = data['Close'].rolling(20).mean()

            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            data['RSI'] = 100 - (100 / (1 + rs))

            # Clean rows with NaN indicators
            clean_data = data.dropna(subset=['SMA5', 'SMA20', 'RSI']).copy()

            if clean_data.empty or len(clean_data) < 7:
                st.warning("Insufficient trading data to complete 7-day context analysis.")
            else:
                last_7_days = clean_data.tail(7)
                today = clean_data.iloc[-1]
                prev = clean_data.iloc[-2]

                today_price = float(today['Close'])

                # 2. Evaluate Today's Signal based on 7-Day Context
                patterns = analyze_7day_patterns(last_7_days)
                bullish_score, bearish_score = 0, 0
                reasons = []

                # Moving Average Crossover
                if float(prev['SMA5']) <= float(prev['SMA20']) and float(today['SMA5']) > float(today['SMA20']):
                    bullish_score += 2
                    reasons.append("Golden Cross: 5-SMA crossed above 20-SMA")
                elif float(prev['SMA5']) >= float(prev['SMA20']) and float(today['SMA5']) < float(today['SMA20']):
                    bearish_score += 2
                    reasons.append("Death Cross: 5-SMA crossed below 20-SMA")

                # RSI Check
                rsi_val = float(today['RSI'])
                if rsi_val < 35:
                    bullish_score += 1
                    reasons.append(f"Oversold RSI ({rsi_val:.1f})")
                elif rsi_val > 65:
                    bearish_score += 1
                    reasons.append(f"Overbought RSI ({rsi_val:.1f})")

                # 7-Day Breakout / Breakdown
                seven_day_max = float(last_7_days['High'].iloc[:-1].max())
                seven_day_min = float(last_7_days['Low'].iloc[:-1].min())

                if today_price > seven_day_max:
                    bullish_score += 1
                    reasons.append("Breakout: Today's price broke above 7-day high.")
                elif today_price < seven_day_min:
                    bearish_score += 1
                    reasons.append("Breakdown: Today's price dropped below 7-day low.")

                # Candlestick Patterns
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

                # 3. Header & Dashboard Banner
                st.subheader(f"Today's Signal Dashboard: {ticker.upper()}")

                if signal == "BUY":
                    st.success("🟢 TODAY'S ACTION: BUY / LONG SETUP")
                elif signal == "SELL":
                    st.error("🔴 TODAY'S ACTION: SELL / SHORT SETUP")
                else:
                    st.info("🟡 TODAY'S ACTION: NEUTRAL / HOLD — No high-probability setup today.")

                # 4. Show Setup Metrics (ONLY for BUY or SELL)
                if signal in ["BUY", "SELL"]:
                    risk_amount = today_price * (risk_percent / 100.0)

                    if signal == "BUY":
                        entry_price = today_price
                        stop_loss = entry_price - risk_amount
                        target_1 = entry_price + (risk_amount * 1.5)
                        target_2 = entry_price + (risk_amount * 3.0)
                    else:  # SELL / SHORT
                        entry_price = today_price
                        stop_loss = entry_price + risk_amount
                        target_1 = entry_price - (risk_amount * 1.5)
                        target_2 = entry_price - (risk_amount * 3.0)

                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Today's Entry", f"${entry_price:.2f}")
                    col2.metric("Stop Loss", f"${stop_loss:.2f}", delta=f"-{risk_percent}%" if signal == "BUY" else f"+{risk_percent}%")
                    col3.metric("Target 1", f"${target_1:.2f}", delta="1:1.5 R/R")
                    col4.metric("Target 2", f"${target_2:.2f}", delta="1:3.0 R/R")
                    col5.metric("RSI (14-Day)", f"{rsi_val:.1f}")

                else:  # NEUTRAL / HOLD
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Today's Close", f"${today_price:.2f}")
                    col2.metric("RSI (14-Day)", f"{rsi_val:.1f}")
                    col3.metric("Status", "Awaiting Setup")

                st.markdown("**Today's Analysis Rationale:**")
                for r in reasons:
                    st.write(f"- {r}")
                if not reasons:
                    st.write("- Market consolidating over the last 7 days. No clear setup today.")

                # 5. Generate 3-Day Forecast Candles
                forecast_df = generate_3day_forecast(today, signal, clean_data.tail(10))

                # 6. Render Chart: Today's Candle + 3 Projected Candles
                today_df = clean_data.tail(1)

                fig = go.Figure()

                # Today's Historical Candle
                fig.add_trace(go.Candlestick(
                    x=today_df.index,
                    open=[float(x) for x in today_df['Open']],
                    high=[float(x) for x in today_df['High']],
                    low=[float(x) for x in today_df['Low']],
                    close=[float(x) for x in today_df['Close']],
                    name="Today's Candle"
                ))

                # 3-Day Projected Candles
                fig.add_trace(go.Candlestick(
                    x=forecast_df.index,
                    open=[float(x) for x in forecast_df['Open']],
                    high=[float(x) for x in forecast_df['High']],
                    low=[float(x) for x in forecast_df['Low']],
                    close=[float(x) for x in forecast_df['Close']],
                    name="3-Day Forecast",
                    increasing_line_color='rgba(0, 230, 118, 0.75)',
                    decreasing_line_color='rgba(255, 61, 0, 0.75)',
                    opacity=0.8
                ))

                # Add Target Horizontal Lines ONLY for BUY or SELL signals
                if signal in ["BUY", "SELL"]:
                    fig.add_hline(y=target_2, line_dash="dash", line_color="green", annotation_text=f"Target 2 (${target_2:.2f})", annotation_position="top right")
                    fig.add_hline(y=target_1, line_dash="dash", line_color="lightgreen", annotation_text=f"Target 1 (${target_1:.2f})", annotation_position="top right")
                    fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", annotation_text=f"Stop Loss (${stop_loss:.2f})", annotation_position="bottom right")

                fig.update_layout(
                    title=f"Today's Candle & 3-Day Forecast for {ticker.upper()}",
                    xaxis_rangeslider_visible=False,
                    template="plotly_white",
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)

        else:
            st.error("Could not fetch data for this ticker. Verify the symbol.")

    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
