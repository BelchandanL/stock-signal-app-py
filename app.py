import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Top 8 Heavy Movers & Multi-Style Signal Dashboard", layout="wide")
st.title("⚡ Top 8 Heavy Movers & Multi-Style Signal Dashboard")

# Popular liquid tickers for scanning top heavy movers
WATCHLIST_TICKERS = ["NVDA", "TSLA", "AMD", "AAPL", "AMZN", "META", "MSFT", "GOOGL", "NFLX", "PLTR", "SPY", "QQQ"]

# Sidebar Selection
st.sidebar.header("Navigation & Settings")
stock_input_mode = st.sidebar.radio(
    "Stock Selection Mode",
    ["Scan Top 8 Heavy Volume Movers", "Manual Ticker Entry"]
)

trade_style = st.sidebar.selectbox(
    "Select Trading Style",
    ["Day Trade (Intraday)", "Swing Trade", "Short-Term (1-4 Weeks)", "Long-Term (Months/Years)"]
)

risk_percent = st.sidebar.slider("Stop Loss Risk %", min_value=0.5, max_value=5.0, value=1.5, step=0.25)

@st.cache_data(ttl=300)
def scan_top8_heavy_movers(ticker_list):
    """Scans watchlist and returns top 8 heavy price movers ranked by volume surge and volatility."""
    movers = []
    for sym in ticker_list:
        try:
            ticker_obj = yf.Ticker(sym)
            df = ticker_obj.history(period="10d", interval="1d")
            if not df.empty and len(df) >= 2:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                latest = df.iloc[-1]
                prev = df.iloc[-2]

                price = float(latest["Close"])
                pct_change = ((price - float(prev["Close"])) / float(prev["Close"])) * 100.0
                day_range = ((float(latest["High"]) - float(latest["Low"])) / float(latest["Low"])) * 100.0
                
                # Volume Surge (Current Volume vs 5-Day Average Volume)
                avg_vol = df["Volume"].tail(5).mean()
                rvol = float(latest["Volume"]) / avg_vol if avg_vol > 0 else 1.0

                movers.append({
                    "Ticker": sym,
                    "Current Price": f"${price:.2f}",
                    "Change %": pct_change,
                    "Intraday Range %": day_range,
                    "Volume Surge (RVOL)": f"{rvol:.2f}x",
                    "Raw_Score": abs(pct_change) * rvol
                })
        except Exception:
            continue

    df_movers = pd.DataFrame(movers)
    if not df_movers.empty:
        # Sort by impact score and strictly limit to Top 8
        df_movers = df_movers.sort_values(by="Raw_Score", ascending=False).head(8).drop(columns=["Raw_Score"])
    return df_movers

def analyze_candlestick_patterns(df):
    """Detects candlestick price action patterns on recent bars."""
    patterns = []
    if len(df) < 2:
        return patterns

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    curr_open, curr_close = float(curr["Open"]), float(curr["Close"])
    curr_high, curr_low = float(curr["High"]), float(curr["Low"])
    prev_open, prev_close = float(prev["Open"]), float(prev["Close"])

    body_size = abs(curr_close - curr_open)
    total_range = curr_high - curr_low
    lower_wick = min(curr_open, curr_close) - curr_low
    upper_wick = curr_high - max(curr_open, curr_close)

    if prev_close < prev_open and curr_close > curr_open and curr_close >= prev_open:
        patterns.append(("BULLISH", "Bullish Engulfing Pattern"))
    if prev_close > prev_open and curr_close < curr_open and curr_close <= prev_open:
        patterns.append(("BEARISH", "Bearish Engulfing Pattern"))
    if total_range > 0 and (lower_wick >= 2 * body_size) and (upper_wick <= 0.2 * body_size) and curr_close > curr_open:
        patterns.append(("BULLISH", "Hammer Reversal Pattern"))
    if total_range > 0 and (upper_wick >= 2 * body_size) and (lower_wick <= 0.2 * body_size) and curr_close < curr_open:
        patterns.append(("BEARISH", "Shooting Star Pattern"))

    return patterns

# Ticker Determination Logic
selected_ticker = "NVDA"

if stock_input_mode == "Scan Top 8 Heavy Volume Movers":
    st.subheader("🔥 Top 8 Heavy Volume Movers & High Volatility Stocks")
    st.caption("Automatically scans key liquid market movers for high relative volume surge (RVOL) and price range.")
    
    with st.spinner("Scanning top 8 heavy market movers..."):
        movers_df = scan_top8_heavy_movers(WATCHLIST_TICKERS)

    if not movers_df.empty:
        # Format percentages for table display
        formatted_df = movers_df.copy()
        formatted_df["Change %"] = formatted_df["Change %"].map(lambda x: f"{x:+.2f}%")
        formatted_df["Intraday Range %"] = formatted_df["Intraday Range %"].map(lambda x: f"{x:.2f}%")
        
        st.dataframe(formatted_df, use_container_width=True)

        # Select stock directly from Top 8 Heavy Movers Scanner
        top_movers_list = movers_df["Ticker"].tolist()
        selected_ticker = st.selectbox("Select one of the Top 8 Heavy Movers to Analyze:", top_movers_list, index=0)
    else:
        st.warning("Could not fetch top 8 scanner data. Defaulting to NVDA.")
        selected_ticker = "NVDA"
else:
    selected_ticker = st.sidebar.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "NVDA")

# Main Analysis & Charting Engine
if selected_ticker:
    try:
        # Determine data period and interval based on Trading Style
        if trade_style == "Day
