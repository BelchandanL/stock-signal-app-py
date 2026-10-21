import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Candle & Technical Signal Analyzer", layout="wide")
st.title("📈 Candlestick Pattern & Technical Indicator Signal Dashboard")

# Sidebar inputs
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "AAPL")
risk_percent = st.sidebar.slider("Stop Loss Risk %", min_value=1.0, max_value=5.0, value=2.0, step=0.5)

def detect_candlestick_patterns(df):
    """Detects basic candlestick chart patterns from recent candles."""
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
    if prev_close < prev_open and curr_close > curr_open and curr_close >= prev_open and curr_open <= prev_close:
        patterns.append(("BULLISH", "Bullish Engulfing (Reversal Signal)"))

    # 2. Bearish Engulfing
    if prev_close > prev_open and curr_close < curr_open and curr_close <= prev_open and curr_open >= prev_close:
        patterns.append(("BEARISH", "Bearish Engulfing (Reversal Signal)"))

    # 3. Hammer (Bullish)
    if total_range > 0 and (lower_wick >= 2 * body_size) and (upper_wick <= 0.2 * body_size) and curr_close > curr_open:
        patterns.append(("BULLISH", "Hammer Pattern (Potential Bottom Reversal)"))

    # 4. Shooting Star (Bearish)
    if total_range > 0 and (upper_wick >= 2 * body_size) and (lower_wick <= 0.2 * body_size) and curr_close < curr_open:
        patterns.append(("BEARISH", "Shooting Star Pattern (Potential Top Reversal)"))

    # 5. Doji (Indecision)
    if total_range > 0 and (body_size / total_range) < 0.1:
        patterns.append(("NEUTRAL", "Doji Candle (Market Indecision)"))

    return patterns

if ticker:
    data = yf.download(ticker, period="60d", interval="1d")
    
    if not data.empty:
        # Flatten MultiIndex columns if returned by yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # 1. Technical Indicators Calculation
        data['SMA5'] = data['Close'].rolling(5).mean()
        data['SMA20'] = data['Close'].rolling(20).mean()
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))

        # 2. Detect Crossover Signals across historical series for Chart Markers
        data['Prev_SMA5'] = data['SMA5'].shift(1)
        data['Prev_SMA20'] = data['SMA20'].shift(1)

        # Crossover logic: Golden Cross (BUY), Death Cross (SELL)
        buy_signals = (data['Prev_SMA5'] <= data['Prev_SMA20']) & (data['SMA5'] > data['SMA20'])
        sell_signals = (data['Prev_SMA5'] >= data['Prev_SMA20']) & (data['SMA5'] < data['SMA20'])

        data['Chart_Signal'] = None
        data.loc[buy_signals, 'Chart_Signal'] = 'BUY'
        data.loc[sell_signals, 'Chart_Signal'] = 'SELL'

        latest = data.iloc[-1]
        prev = data.iloc[-2]
        current_price = float(latest['Close'])

        # 3. Candlestick Pattern Detection on Latest Candle
        detected_patterns = detect_candlestick_patterns(data)

        # 4. Combined Signal Evaluation (SMA + RSI + Candle Patterns)
        bullish_score = 0
        bearish_score = 0
        reasons = []

        if prev['SMA5'] <= prev['SMA20'] and latest['SMA5'] > latest['SMA20']:
            bullish_score += 2
            reasons.append("Golden Cross: 5-Day SMA crossed above 20-Day SMA.")
        elif prev['SMA5'] >= prev['SMA20'] and latest['SMA5'] < latest['SMA20']:
            bearish_score += 2
            reasons.append("Death Cross: 5-Day SMA crossed below 20-Day SMA.")

        if latest['RSI'] < 30:
            bullish_score += 1
            reasons.append(f"Oversold RSI ({latest['RSI']:.1f}).")
        elif latest['RSI'] > 70:
            bearish_score += 1
            reasons.append(f"Overbought RSI ({latest['RSI']:.1f}).")

        for bias, p_name in detected_patterns:
            if bias == "BULLISH":
                bullish_score += 1
                reasons.append(f"Candle Pattern: {p_name}")
            elif bias == "BEARISH":
                bearish_score += 1
                reasons.append(f"Candle Pattern: {p_name}")
            else:
                reasons.append(f"Candle Pattern: {p_name}")

        # Final Verdict
        if bullish_score > bearish_score and bullish_score >= 2:
            signal = "BUY"
        elif bearish_score > bullish_score and bearish_score >= 2:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        # 5. Display Signal Banner
        st.subheader(f"Signal Dashboard for {ticker.upper()}")
        
        if signal == "BUY":
            st.success("🟢 RECOMMENDED ACTION: BUY / LONG")
        elif signal == "SELL":
            st.error("🔴 RECOMMENDED ACTION: SELL / SHORT")
        else:
            st.info("🟡 RECOMMENDED ACTION: NEUTRAL / HOLD — No clear trade setup.")

        # 6. Calculate & Display Metrics (Targets ONLY shown for BUY or SELL)
        if signal in ["BUY", "SELL"]:
            risk_amount = current_price * (risk_percent / 100.0)

            if signal == "BUY":
                entry_price = current_price
                stop_loss = entry_price - risk_amount
                target_1 = entry_price + (risk_amount * 1.5)
                target_2 = entry_price + (risk_amount * 3.0)
            else:  # SELL / SHORT
                entry_price = current_price
                stop_loss = entry_price + risk_amount
                target_1 = entry_price - (risk_amount * 1.5)
                target_2 = entry_price - (risk_amount * 3.0)

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Entry Price", f"${entry_price:.2f}")
            col2.metric("Stop Loss (SL)", f"${stop_loss:.2f}", delta=f"-{risk_percent}%" if signal == "BUY" else f"+{risk_percent}%")
            col3.metric("Target 1 (TP1)", f"${target_1:.2f}", delta="1 : 1.5 R/R")
            col4.metric("Target 2 (TP2)", f"${target_2:.2f}", delta="1 : 3.0 R/R")
            col5.metric("RSI (14-Day)", f"{latest['RSI']:.1f}")

        else:  # NEUTRAL / HOLD — Hide Target 1, Target 2, and Stop Loss
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"${current_price:.2f}")
            col2.metric("RSI (14-Day)", f"{latest['RSI']:.1f}")
            col3.metric("Trade Status", "Awaiting Setup")

        st.markdown("**Signal Rationale & Candle Analysis:**")
        for r in reasons:
            st.write(f"- {r}")
        if not reasons:
            st.write("- Market consolidation. No actionable technical triggers detected.")

        # 7. Interactive Candlestick Chart with Signal Annotations & Markers
        fig = go.Figure()

        # Candlestick Series
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'], high=data['High'],
            low=data['Low'], close=data['Close'], name="OHLC"
        ))

        # Moving Averages
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA5'], line=dict(color='blue', width=1), name='5-Day SMA'))
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], line=dict(color='orange', width=1), name='20-Day SMA'))

        # Add BUY Signal Markers on Chart (Green Up Triangles below Low price)
        buy_points = data[data['Chart_Signal'] == 'BUY']
        if not buy_points.empty:
            fig.add_trace(go.Scatter(
                x=buy_points.index,
                y=buy_points['Low'] * 0.98,
                mode='markers+text',
                marker=dict(symbol='triangle-up', size=14, color='green'),
                text=['BUY'] * len(buy_points),
                textposition='bottom center',
                name='Buy Signal Marker'
            ))

        # Add SELL Signal Markers on Chart (Red Down Triangles above High price)
        sell_points = data[data['Chart_Signal'] == 'SELL']
        if not sell_points.empty:
            fig.add_trace(go.Scatter(
                x=sell_points.index,
                y=sell_points['High'] * 1.02,
                mode='markers+text',
                marker=dict(symbol='triangle-down', size=14, color='red'),
                text=['SELL'] * len(sell_points),
                textposition='top center',
                name='Sell Signal Marker'
            ))

        # Plot Target lines ONLY if there is an active BUY or SELL signal
        if signal in ["BUY", "SELL"]:
            fig.add_hline(y=target_2, line_dash="dash", line_color="green", annotation_text=f"Target 2 (${target_2:.2f})", annotation_position="top right")
            fig.add_hline(y=target_1, line_dash="dash", line_color="lightgreen", annotation_text=f"Target 1 (${target_1:.2f})", annotation_position="top right")
            fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", annotation_text=f"Stop Loss (${stop_loss:.2f})", annotation_position="bottom right")

        fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=550)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Could not fetch data for this ticker. Verify the ticker symbol.")
