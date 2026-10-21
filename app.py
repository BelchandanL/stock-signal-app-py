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
    # Fetch 200 days for long-term indicators (SMA 50/200)
    data = yf.download(ticker, period="200d", interval="1d")
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # 1. Technical Indicators
        data['SMA5'] = data['Close'].rolling(5).mean()
        data['SMA20'] = data['Close'].rolling(20).mean()
        data['SMA50'] = data['Close'].rolling(50).mean()
        data['SMA200'] = data['Close'].rolling(200).mean()

        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))

        # Crossover logic for chart history
        data['Prev_SMA5'] = data['SMA5'].shift(1)
        data['Prev_SMA20'] = data['SMA20'].shift(1)
        data['Chart_Signal'] = None
        data.loc[(data['Prev_SMA5'] <= data['Prev_SMA20']) & (data['SMA5'] > data['SMA20']), 'Chart_Signal'] = 'BUY'
        data.loc[(data['Prev_SMA5'] >= data['Prev_SMA20']) & (data['SMA5'] < data['SMA20']), 'Chart_Signal'] = 'SELL'

        # Filter last 30 days for displaying on chart, but evaluate 7-day recent trends
        data_display = data.tail(30).copy()
        recent_7d = data.tail(7)
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        current_price = float(latest['Close'])

        # 2. Setup Evaluation: Long-Term vs Swing Trade
        sma50 = float(latest['SMA50']) if not pd.isna(latest['SMA50']) else current_price
        sma200 = float(latest['SMA200']) if not pd.isna(latest['SMA200']) else current_price

        long_term_bullish = (current_price > sma50) and (sma50 > sma200)
        setup_type = "LONG-TERM INVESTOR SETUP" if long_term_bullish else "SWING TRADE SETUP"

        # 3. 7-Day Pattern Analysis & Signal Score
        detected_patterns = detect_7day_patterns(data)
        bullish_score, bearish_score = 0, 0
        reasons = []

        if prev['SMA5'] <= prev['SMA20'] and latest['SMA5'] > latest['SMA20']:
            bullish_score += 2
            reasons.append("Golden Cross: 5-Day SMA crossed above 20-Day SMA.")
        elif prev['SMA5'] >= prev['SMA20'] and latest['SMA5'] < latest['SMA20']:
            bearish_score += 2
            reasons.append("Death Cross: 5-Day SMA crossed below 20-Day SMA.")

        if latest['RSI'] < 35:
            bullish_score += 1
            reasons.append(f"Oversold RSI ({latest['RSI']:.1f}).")
        elif latest['RSI'] > 65:
            bearish_score += 1
            reasons.append(f"Overbought RSI ({latest['RSI']:.1f}).")

        for bias, p_name in detected_patterns:
            if bias == "BULLISH":
                bullish_score += 1
                reasons.append(f"7-Day Pattern: {p_name}")
            elif bias == "BEARISH":
                bearish_score += 1
                reasons.append(f"7-Day Pattern: {p_name}")

        # Final Signal Verdict
        if bullish_score > bearish_score and bullish_score >= 2:
            signal = "BUY"
        elif bearish_score > bullish_score and bearish_score >= 2:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        # 4. Display Header & Dashboard Banner
        st.subheader(f"7-Day Signal Dashboard: {ticker.upper()}")
        st.caption(f"📍 Active Mode: **{setup_type}** | 50-SMA: ${sma50:.2f} | 200-SMA: ${sma200:.2f}")

        if signal == "BUY":
            st.success(f"🟢 RECOMMENDED ACTION: BUY ({setup_type})")
        elif signal == "SELL":
            st.error(f"🔴 RECOMMENDED ACTION: SELL ({setup_type})")
        else:
            st.info("🟡 RECOMMENDED ACTION: NEUTRAL / HOLD — Awaiting clear 7-day trigger.")

        # 5. Metrics & Target Calculations (Hidden for NEUTRAL)
        if signal in ["BUY", "SELL"]:
            # Long-term uses wider targets (2.5x and 5.0x risk), Swing uses (1.5x and 3.0x risk)
            multiplier_t1 = 2.5 if setup_type == "LONG-TERM INVESTOR SETUP" else 1.5
            multiplier_t2 = 5.0 if setup_type == "LONG-TERM INVESTOR SETUP" else 3.0

            risk_amount = current_price * (risk_percent / 100.0)

            if signal == "BUY":
                entry_price = current_price
                stop_loss = entry_price - risk_amount
                target_1 = entry_price + (risk_amount * multiplier_t1)
                target_2 = entry_price + (risk_amount * multiplier_t2)
            else:  # SELL / SHORT
                entry_price = current_price
                stop_loss = entry_price + risk_amount
                target_1 = entry_price - (risk_amount * multiplier_t1)
                target_2 = entry_price - (risk_amount * multiplier_t2)

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Buy / Entry Price", f"${entry_price:.2f}")
            col2.metric("Stop Loss (SL)", f"${stop_loss:.2f}", delta=f"-{risk_percent}%" if signal == "BUY" else f"+{risk_percent}%")
            col3.metric("Target 1 (TP1)", f"${target_1:.2f}", delta=f"1 : {multiplier_t1} R/R")
            col4.metric("Target 2 (TP2)", f"${target_2:.2f}", delta=f"1 : {multiplier_t2} R/R")
            col5.metric("7-Day RSI", f"{latest['RSI']:.1f}")

        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"${current_price:.2f}")
            col2.metric("7-Day RSI", f"{latest['RSI']:.1f}")
            col3.metric("Trade Setup", "Consolidating")

        st.markdown("**7-Day Analysis & Rationale:**")
        for r in reasons:
            st.write(f"- {r}")
        if not reasons:
            st.write("- Market consolidation over the last 7 days. No high-probability trigger.")

        # 6. Generate Future Projection Candles
        df_future = generate_future_candles(latest, signal, days=5)

        # 7. Chart Rendering
        fig = go.Figure()

        # Historical Candlesticks (30 Days)
        fig.add_trace(go.Candlestick(
            x=data_display.index,
            open=data_display['Open'], high=data_display['High'],
            low=data_display['Low'], close=data_display['Close'], name="Actual OHLC"
        ))

        # Projected Future Candlesticks (5 Days ahead)
        fig.add_trace(go.Candlestick(
            x=df_future.index,
            open=df_future['Open'], high=df_future['High'],
            low=df_future['Low'], close=df_future['Close'],
            name="Projected Future Candles",
            increasing_line_color='cyan', decreasing_line_color='magenta',
            opacity=0.75
        ))

        # Moving Average Lines
        fig.add_trace(go.Scatter(x=data_display.index, y=data_display['SMA5'], line=dict(color='blue', width=1), name='5-Day SMA'))
        fig.add_trace(go.Scatter(x=data_display.index, y=data_display['SMA20'], line=dict(color='orange', width=1), name='20-Day SMA'))

        # On-Chart Historical Signal Markers
        buy_pts = data_display[data_display['Chart_Signal'] == 'BUY']
        if not buy_pts.empty:
            fig.add_trace(go.Scatter(
                x=buy_pts.index, y=buy_pts['Low'] * 0.98,
                mode='markers+text', marker=dict(symbol='triangle-up', size=14, color='green'),
                text=['BUY'] * len(buy_pts), textposition='bottom center', name='Buy Trigger'
            ))

        sell_pts = data_display[data_display['Chart_Signal'] == 'SELL']
        if not sell_pts.empty:
            fig.add_trace(go.Scatter(
                x=sell_pts.index, y=sell_pts['High'] * 1.02,
                mode='markers+text', marker=dict(symbol='triangle-down', size=14, color='red'),
                text=['SELL'] * len(sell_pts), textposition='top center', name='Sell Trigger'
            ))

        # Horizontal Target Lines (Active setups only)
        if signal in ["BUY", "SELL"]:
            fig.add_hline(y=target_2, line_dash="dash", line_color="green", annotation_text=f"Target 2 (${target_2:.2f})", annotation_position="top right")
            fig.add_hline(y=target_1, line_dash="dash", line_color="lightgreen", annotation_text=f"Target 1 (${target_1:.2f})", annotation_position="top right")
            fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", annotation_text=f"Stop Loss (${stop_loss:.2f})", annotation_position="bottom right")

        fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=580)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Could not fetch stock data for this ticker.")
