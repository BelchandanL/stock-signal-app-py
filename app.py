import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Signal Dashboard", layout="wide")
st.title("📈 Stock Candlestick & Trading Signal Analyzer")

ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "AAPL")

if ticker:
    data = yf.download(ticker, period="60d", interval="1d")
    
    if not data.empty:
        # Handle multi-index columns if returned by yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # 1. Technical Indicators
        data['SMA5'] = data['Close'].rolling(5).mean()
        data['SMA20'] = data['Close'].rolling(20).mean()
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        # 2. Signal Evaluation
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
            reasons.append(f"RSI is Oversold ({latest['RSI']:.1f}).")
        elif latest['RSI'] > 70:
            signal = "SELL" if signal != "BUY" else "NEUTRAL"
            reasons.append(f"RSI is Overbought ({latest['RSI']:.1f}).")

        # Display Signal Metric
        col1, col2, col3 = st.columns(3)
        col1.metric("Latest Close", f"${latest['Close']:.2f}")
        col2.metric("RSI (14-Day)", f"{latest['RSI']:.1f}")
        col3.metric("Trade Signal", signal)

        st.subheader("Signal Breakdown")
        for r in reasons:
            st.write(f"- {r}")
        if not reasons:
            st.write("- No critical triggers detected today.")

        # Candlestick Chart
        fig = go.Figure(data=[
            go.Candlestick(
                x=data.index,
                open=data['Open'], high=data['High'],
                low=data['Low'], close=data['Close'], name="OHLC"
            ),
            go.Scatter(x=data.index, y=data['SMA5'], line=dict(color='blue', width=1), name='5-Day SMA'),
            go.Scatter(x=data.index, y=data['SMA20'], line=dict(color='orange', width=1), name='20-Day SMA')
        ])
        fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Could not fetch data for this ticker. Check the symbol and try again.")