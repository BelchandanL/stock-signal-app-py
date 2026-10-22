import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Top 8 Heavy Movers & Multi-Style Signal Dashboard", layout="wide")

# Watchlist of highly liquid stocks for scanning top heavy movers
WATCHLIST_TICKERS = ["NVDA", "TSLA", "AMD", "AAPL", "AMZN", "META", "MSFT", "GOOGL", "NFLX", "PLTR", "SPY", "QQQ"]

# Sidebar Mode Selection
st.sidebar.header("Navigation")
navigation_mode = st.sidebar.radio(
    "Choose Mode",
    ["Scan Top 8 Heavy Volume Movers", "Manual Ticker Entry"]
)

@st.cache_data(ttl=300)
def scan_top8_heavy_movers(ticker_list):
    """Scans watchlist and returns top 8 heavy price movers strictly sorted in descending order."""
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
                
                # Relative Volume Surge (Current Volume vs 5-Day Average Volume)
                avg_vol = df["Volume"].tail(5).mean()
                rvol = float(latest["Volume"]) / avg_vol if avg_vol > 0 else 1.0

                # Score combines raw volatility and relative volume surge
                impact_score = abs(pct_change) * rvol

                movers.append({
                    "Ticker": sym,
                    "Current Price": price,
                    "Change %": pct_change,
                    "Intraday Range %": day_range,
                    "Volume Surge (RVOL)": rvol,
                    "Score": impact_score
                })
        except Exception:
            continue

    df_movers = pd.DataFrame(movers)
    if not df_movers.empty:
        # Sort strictly in descending order by impact score and keep top 8
        df_movers = df_movers.sort_values(by="Score", ascending=False).head(8).reset_index(drop=True)
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


# MODE 1: SCAN TOP 8 HEAVY MOVERS
if navigation_mode == "Scan Top 8 Heavy Volume Movers":
    st.title("🔥 Top 8 Heavy Volume & Price Movers Scanner")
    st.caption("Real-time ranking of top market movers sorted strictly from highest market impact to lowest.")

    with st.spinner("Scanning top 8 heavy market movers..."):
        movers_df = scan_top8_heavy_movers(WATCHLIST_TICKERS)

    if not movers_df.empty:
        # Prepare display copy formatted properly
        display_df = movers_df.copy()
        display_df["Rank"] = range(1, len(display_df) + 1)
        display_df["Current Price"] = display_df["Current Price"].map(lambda x: f"${x:.2f}")
        display_df["Change %"] = display_df["Change %"].map(lambda x: f"{x:+.2f}%")
        display_df["Intraday Range %"] = display_df["Intraday Range %"].map(lambda x: f"{x:.2f}%")
        display_df["Volume Surge (RVOL)"] = display_df["Volume Surge (RVOL)"].map(lambda x: f"{x:.2f}x")

        # Reorder columns for optimal view
        display_df = display_df[["Rank", "Ticker", "Current Price", "Change %", "Intraday Range %", "Volume Surge (RVOL)"]]
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        selected_ticker = st.selectbox(
            "Select one of the Top 8 Heavy Movers to inspect trade setup:",
            movers_df["Ticker"].tolist(),
            index=0
        )
        trade_style = "Day Trade (Intraday)"
        risk_percent = 1.5
    else:
        st.warning("Could not fetch heavy movers data. Try switching modes.")
        selected_ticker = "NVDA"
        trade_style = "Day Trade (Intraday)"
        risk_percent = 1.5

# MODE 2: MANUAL TICKER ENTRY
else:
    st.title("⚡ Manual Stock Signal & Chart Analyzer")
    selected_ticker = st.sidebar.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA):", "NVDA")
    
    trade_style = st.sidebar.selectbox(
        "Select Trading Style",
        ["Day Trade (Intraday)", "Swing Trade", "Short-Term (1-4 Weeks)", "Long-Term (Months/Years)"]
    )
    risk_percent = st.sidebar.slider("Stop Loss Risk %", min_value=0.5, max_value=5.0, value=1.5, step=0.25)


# MAIN TECHNICAL ANALYSIS & CHART ENGINE
if selected_ticker:
    try:
        if trade_style == "Day Trade (Intraday)":
            period_val, interval_val = "5d", "5m"
            fast_ma, slow_ma = "SMA5", "SMA20"
            r_mult1, r_mult2 = 1.5, 3.0
        elif trade_style == "Swing Trade":
            period_val, interval_val = "10d", "15m"
            fast_ma, slow_ma = "SMA5", "SMA20"
            r_mult1, r_mult2 = 1.5, 3.0
        elif trade_style == "Short-Term (1-4 Weeks)":
            period_val, interval_val = "60d", "1d"
            fast_ma, slow_ma = "SMA5", "SMA20"
            r_mult1, r_mult2 = 2.0, 4.0
        else:  # Long-Term
            period_val, interval_val = "200d", "1d"
            fast_ma, slow_ma = "SMA50", "SMA200"
            r_mult1, r_mult2 = 2.5, 5.0

        data = yf.download(selected_ticker.strip().upper(), period=period_val, interval=interval_val)
        
        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            data["SMA5"] = data["Close"].rolling(5).mean()
            data["SMA20"] = data["Close"].rolling(20).mean()
            if trade_style == "Long-Term (Months/Years)":
                data["SMA50"] = data["Close"].rolling(50).mean()
                data["SMA200"] = data["Close"].rolling(200).mean()

            delta = data["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            data["RSI"] = 100 - (100 / (1 + rs))

            clean_data = data.dropna(subset=[fast_ma, slow_ma, "RSI"]).copy()

            if not clean_data.empty and len(clean_data) >= 2:
                if "Intraday" in trade_style:
                    latest_date = clean_data.index[-1].date()
                    display_data = clean_data[clean_data.index.date == latest_date].copy()
                    if display_data.empty or len(display_data) < 2:
                        display_data = clean_data.tail(35).copy()
                else:
                    display_data = clean_data.tail(40).copy()

                latest_bar = clean_data.iloc[-1]
                prev_bar = clean_data.iloc[-2]
                current_price = float(latest_bar["Close"])

                # Signal Calculations
                patterns = analyze_candlestick_patterns(clean_data)
                bullish_score, bearish_score = 0, 0
                reasons = []

                if float(prev_bar[fast_ma]) <= float(prev_bar[slow_ma]) and float(latest_bar[fast_ma]) > float(latest_bar[slow_ma]):
                    bullish_score += 2
                    reasons.append(f"Golden Cross: {fast_ma} crossed above {slow_ma}")
                elif float(prev_bar[fast_ma]) >= float(prev_bar[slow_ma]) and float(latest_bar[fast_ma]) < float(latest_bar[slow_ma]):
                    bearish_score += 2
                    reasons.append(f"Death Cross: {fast_ma} crossed below {slow_ma}")

                if float(latest_bar[fast_ma]) > float(latest_bar[slow_ma]):
                    bullish_score += 1
                    reasons.append(f"Trend is Bullish ({fast_ma} > {slow_ma})")
                elif float(latest_bar[fast_ma]) < float(latest_bar[slow_ma]):
                    bearish_score += 1
                    reasons.append(f"Trend is Bearish ({fast_ma} < {slow_ma})")

                rsi_val = float(latest_bar["RSI"])
                if rsi_val < 35:
                    bullish_score += 1
                    reasons.append(f"Oversold RSI ({rsi_val:.1f})")
                elif rsi_val > 65:
                    bearish_score += 1
                    reasons.append(f"Overbought RSI ({rsi_val:.1f})")

                for bias, p_name in patterns:
                    if bias == "BULLISH":
                        bullish_score += 1
                        reasons.append(f"Pattern: {p_name}")
                    elif bias == "BEARISH":
                        bearish_score += 1
                        reasons.append(f"Pattern: {p_name}")

                if bullish_score > bearish_score:
                    signal = "BUY"
                elif bearish_score > bullish_score:
                    signal = "SELL"
                else:
                    signal = "BUY"

                # Dashboard Output
                st.subheader(f"Setup Dashboard: {selected_ticker.upper()} ({trade_style})")

                if signal == "BUY":
                    st.success(f"🟢 RECOMMENDED ACTION: BUY / LONG SETUP")
                else:
                    st.error(f"🔴 RECOMMENDED ACTION: SELL / SHORT SETUP")

                risk_amount = current_price * (risk_percent / 100.0)

                if signal == "BUY":
                    entry_price = current_price
                    stop_loss = entry_price - risk_amount
                    target_1 = entry_price + (risk_amount * r_mult1)
                    target_2 = entry_price + (risk_amount * r_mult2)
                else:
                    entry_price = current_price
                    stop_loss = entry_price + risk_amount
                    target_1 = entry_price - (risk_amount * r_mult1)
                    target_2 = entry_price - (risk_amount * r_mult2)

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Current Entry", f"${entry_price:.2f}")
                col2.metric("Stop Loss", f"${stop_loss:.2f}", delta=f"-{risk_percent}%" if signal == "BUY" else f"+{risk_percent}%")
                col3.metric("Target 1", f"${target_1:.2f}", delta=f"1:{r_mult1} R/R")
                col4.metric("Target 2", f"${target_2:.2f}", delta=f"1:{r_mult2} R/R")
                col5.metric("RSI", f"{rsi_val:.1f}")

                st.markdown("**Signal Rationale:**")
                for r in reasons:
                    st.write(f"- {r}")

                # Plotly Chart
                fig = go.Figure()

                fig.add_trace(go.Candlestick(
                    x=display_data.index,
                    open=[float(x) for x in display_data["Open"]],
                    high=[float(x) for x in display_data["High"]],
                    low=[float(x) for x in display_data["Low"]],
                    close=[float(x) for x in display_data["Close"]],
                    name="Price Candles"
                ))

                fig.add_trace(go.Scatter(x=display_data.index, y=display_data[fast_ma], line=dict(color="blue", width=1.5), name=fast_ma))
                fig.add_trace(go.Scatter(x=display_data.index, y=display_data[slow_ma], line=dict(color="orange", width=1.5), name=slow_ma))

                fig.add_hline(y=target_2, line_dash="dash", line_color="green", annotation_text=f"Target 2 (${target_2:.2f})", annotation_position="top right")
                fig.add_hline(y=target_1, line_dash="dash", line_color="lightgreen", annotation_text=f"Target 1 (${target_1:.2f})", annotation_position="top right")
                fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", annotation_text=f"Stop Loss (${stop_loss:.2f})", annotation_position="bottom right")

                fig.update_layout(
                    title=f"Candlestick Chart ({interval_val}) for {selected_ticker.upper()}",
                    xaxis_rangeslider_visible=False,
                    template="plotly_white",
                    height=550
                )
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error executing analysis: {str(e)}")
