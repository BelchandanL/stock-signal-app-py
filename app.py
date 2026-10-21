import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Signal & Target Analyzer", layout="wide")
st.title("📈 Stock Technical Signals with Targets & Stop Loss")

# Sidebar settings
ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "AAPL")
risk_percent = st.sidebar.slider("Stop Loss Risk %", min_value=1.0, max_value=5.0, value=2.0, step=0.5)

if ticker:
    data = yf.download(ticker, period="60d", interval="1d")
    
    if not data.empty:
        # Standardize DataFrame columns if multi-indexed
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

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        current_price = float(latest['Close'])

        # 2. Determine Buy/Sell Signal
        signal = "NEUTRAL"
        reasons = []

        if prev['SMA5'] <= prev['SMA20'] and latest['SMA5'] > latest['SMA20']:
            signal = "BUY"
            reasons.append("Golden Cross: 5-Day SMA crossed above 20-Day SMA.")
        elif prev['SMA5'] >= prev['SMA20'] and latest['SMA5'] < latest['SMA20']:
            signal = "SELL"
            reasons.append("Death Cross: 5-Day SMA crossed below 20-Day SMA.")

        if latest['RSI'] < 30:
            signal = "BUY" if signal != "SELL" else "NEUTRAL"
            reasons.append(f"Oversold RSI ({latest['RSI']:.1f}).")
        elif latest['RSI'] > 70:
            signal = "SELL" if signal != "BUY" else "NEUTRAL"
            reasons.append(f"Overbought RSI ({latest['RSI']:.1f}).")

        # 3. Calculate Entry, Targets, and Stop Loss
        risk_amount = current_price * (risk_percent / 100.0)

        if signal == "BUY":
            entry_price = current_price
            stop_loss = entry_price - risk_amount
            target_1 = entry_price + (risk_amount * 1.5)  # 1:1.5 Risk-Reward
            target_2 = entry_price + (risk_amount * 3.0)  # 1:3.0 Risk-Reward
        elif signal == "SELL":
            entry_price = current_price
            stop_loss = entry_price + risk_amount
            target_1 = entry_price - (risk_amount * 1.5)
            target_2 = entry_price - (risk_amount * 3.0)
        else: # NEUTRAL
            entry_price = current_price
            stop_loss = current_price - risk_amount
            target_1 = current_price + (risk_amount * 1.5)
            target_2 = current_price + (risk_amount * 3.0)

        # 4. Display Signal Banner & Dashboard Metrics
        st.subheader(f"Signal Dashboard for {ticker.upper()}")
        
        # Color badge logic
        if signal == "BUY":
            st.success("🟢 RECOMMENDED ACTION: BUY / LONG")
        elif signal == "SELL":
            st.error("🔴 RECOMMENDED ACTION: SELL / SHORT")
        else:
            st.info("🟡 RECOMMENDED ACTION: NEUTRAL / HOLD")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Entry Price", f"${entry_price:.2f}")
        col2.metric("Stop Loss (SL)", f"${stop_loss:.2f}", delta=f"-{risk_percent}%" if signal != "SELL" else f"+{risk_percent}%")
        col3.metric("Target 1 (TP1)", f"${target_1:.2f}", delta="1 : 1.5 R/R")
        col4.metric("Target 2 (TP2)", f"${target_2:.2f}", delta="1 : 3.0 R/R")
        col5.metric("RSI (14-Day)", f"{latest['RSI']:.1f}")

        st.markdown("**Signal Rationale:**")
        for r in reasons:
            st.write(f"- {r}")
        if not reasons:
            st.write("- Market consolidation. No immediate entry trigger.")

        # 5. Interactive Candlestick Chart with Overlay Levels
        fig = go.Figure(data=[
            go.Candlestick(
                x=data.index,
                open=data['Open'], high=data['High'],
                low=data['Low'], close=data['Close'], name="OHLC"
            ),
            go.Scatter(x=data.index, y=data['SMA5'], line=dict(color='blue', width=1), name='5-Day SMA'),
            go.Scatter(x=data.index, y=data['SMA20'], line=dict(color='orange', width=1), name='20-Day SMA')
        ])

        # Plot Stop Loss and Target horizontal lines
        fig.add_hline(y=target_2, line_dash="dash", line_color="green", annotation_text="Target 2", annotation_position="top right")
        fig.add_hline(y=target_1, line_dash="dash", line_color="lightgreen", annotation_text="Target 1", annotation_position="top right")
        fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", annotation_text="Stop Loss", annotation_position="bottom right")

        fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=500)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Could not fetch data for this ticker. Verify the ticker symbol.")
