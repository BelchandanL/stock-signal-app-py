import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Top 10 Heavy Movers & Multi-Style Signal Dashboard", layout="wide")

# Active Market Movers Watchlist
WATCHLIST_TICKERS = ["NVDA", "TSLA", "AMD", "AAPL", "AMZN", "META", "MSFT", "GOOGL", "NFLX", "PLTR", "SPY", "QQQ", "SMCI", "COIN", "MARA", "BA", "BABA", "ARM"]

# Sidebar Mode Navigation
st.sidebar.header("Navigation")
navigation_mode = st.sidebar.radio(
    "Choose Mode",
    ["Scan Top 10 Heavy Volume Movers", "Manual Ticker Entry"]
)

def fetch_put_call_ratio(ticker_symbol):
    """Fetches the nearest option chain and calculates the Volume Put/Call Ratio (PCR)."""
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        options_expirations = ticker_obj.options
        
        if not options_expirations:
            return None, "No Options Data"

        nearest_exp = options_expirations[0]
        opt_chain = ticker_obj.option_chain(nearest_exp)

        calls = opt_chain.calls
        puts = opt_chain.puts

        total_call_vol = calls["volume"].fillna(0).sum()
        total_put_vol = puts["volume"].fillna(0).sum()

        pcr = total_put_vol / total_call_vol if total_call_vol > 0 else 1.0

        if pcr > 1.2:
            sentiment = f"Heavy Bearish Puts ({pcr:.2f})"
        elif pcr < 0.6:
            sentiment = f"Heavy Bullish Calls ({pcr:.2f})"
        else:
            sentiment = f"Neutral ({pcr:.2f})"

        return round(pcr, 2), sentiment

    except Exception:
        return None, "Options Unavailable"


def fetch_cash_flow_sentiment(ticker_symbol):
    """Fetches Operating Cash Flow and Free Cash Flow to determine Cash Flow Sentiment."""
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        cf = ticker_obj.cashflow
        info = ticker_obj.info

        if cf is None or cf.empty:
            return None, "N/A (ETFs/Indices)"

        # Get Operating Cash Flow & Free Cash Flow
        operating_cf = None
        free_cf = None

        if "Operating Cash Flow" in cf.index:
            operating_cf = cf.loc["Operating Cash Flow"].iloc[0]
        elif "Total Cash From Operating Activities" in cf.index:
            operating_cf = cf.loc["Total Cash From Operating Activities"].iloc[0]

        if "Free Cash Flow" in cf.index:
            free_cf = cf.loc["Free Cash Flow"].iloc[0]

        mcap = info.get("marketCap", None)

        if free_cf and mcap and mcap > 0:
            fcf_yield = (free_cf / mcap) * 100.0
            if fcf_yield > 4.0:
                sentiment = f"Strong Cash Generation (Yield: {fcf_yield:.1f}%)"
            elif fcf_yield > 0:
                sentiment = f"Positive Cash Flow (Yield: {fcf_yield:.1f}%)"
            else:
                sentiment = f"Cash Burn / Negative Yield ({fcf_yield:.1f}%)"
            return round(fcf_yield, 2), sentiment

        elif operating_cf and operating_cf > 0:
            return 1.0, "Positive Operating Cash Flow"
        elif operating_cf and operating_cf < 0:
            return -1.0, "Negative Operating Cash Flow"
        else:
            return None, "Neutral Cash Flow"

    except Exception:
        return None, "Cash Flow Unavailable"


@st.cache_data(ttl=300)
def scan_top10_heavy_movers(ticker_list):
    """Scans watchlist and ranks stocks based on RVOL, % Change, Share Float, and ATR(14)."""
    movers = []
    for sym in ticker_list:
        try:
            ticker_obj = yf.Ticker(sym)
            df = ticker_obj.history(period="30d", interval="1d")
            
            if not df.empty and len(df) >= 15:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                latest = df.iloc[-1]
                prev = df.iloc[-2]

                price = float(latest["Close"])
                pct_change = ((price - float(prev["Close"])) / float(prev["Close"])) * 100.0
                curr_volume = int(latest["Volume"])

                avg_vol_10d = df["Volume"].tail(10).mean()
                rvol = float(curr_volume) / avg_vol_10d if avg_vol_10d > 0 else 1.0

                high_low = df["High"] - df["Low"]
                high_prev_close = (df["High"] - df["Close"].shift(1)).abs()
                low_prev_close = (df["Low"] - df["Close"].shift(1)).abs()
                tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
                atr_14 = float(tr.rolling(14).mean().iloc[-1])
                atr_pct = (atr_14 / price) * 100.0

                info = ticker_obj.info
                float_shares = info.get("floatShares", None)
                if float_shares and float_shares > 0:
                    float_fmt = f"{float_shares / 1e6:.1f}M"
                    float_mult = 1.5 if float_shares < 100e6 else 1.0
                else:
                    float_fmt = "N/A"
                    float_mult = 1.0

                impact_score = abs(pct_change) * rvol * atr_pct * float_mult

                movers.append({
                    "Ticker": sym,
                    "Price": price,
                    "Change %": pct_change,
                    "Current Volume": curr_volume,
                    "RVOL": rvol,
                    "ATR (14)": atr_14,
                    "ATR %": atr_pct,
                    "Share Float": float_fmt,
                    "Score": impact_score
                })
        except Exception:
            continue

    df_movers = pd.DataFrame(movers)
    if not df_movers.empty:
        df_movers = df_movers.sort_values(by="Score", ascending=False).head(10).reset_index(drop=True)
    return df_movers

def analyze_candlestick_patterns(df):
    """Detects primary reversal candlestick patterns."""
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
        patterns.append(("BULLISH", "Bullish Engulfing"))
    if prev_close > prev_open and curr_close < curr_open and curr_close <= prev_open:
        patterns.append(("BEARISH", "Bearish Engulfing"))
    if total_range > 0 and (lower_wick >= 2 * body_size) and (upper_wick <= 0.2 * body_size) and curr_close > curr_open:
        patterns.append(("BULLISH", "Hammer Reversal"))
    if total_range > 0 and (upper_wick >= 2 * body_size) and (lower_wick <= 0.2 * body_size) and curr_close < curr_open:
        patterns.append(("BEARISH", "Shooting Star"))

    return patterns

def evaluate_style_signal(ticker_symbol, style_name, risk_percent, pcr_val, pcr_sentiment, cf_yield, cf_sentiment):
    """Evaluates quantitative signal setup across technicals, options PCR, and cash flow sentiment."""
    style_configs = {
        "Scalping (15m ORB + 1m)": {"period": "1d", "interval": "1m", "fast": "EMA9", "slow": "EMA21", "r1": 1.0, "r2": 2.0},
        "Day Trade (Intraday)": {"period": "5d", "interval": "5m", "fast": "SMA5", "slow": "SMA20", "r1": 1.5, "r2": 3.0},
        "Swing Trade": {"period": "10d", "interval": "15m", "fast": "SMA5", "slow": "SMA20", "r1": 1.5, "r2": 3.0},
        "Short-Term (1-4 Weeks)": {"period": "60d", "interval": "1d", "fast": "SMA5", "slow": "SMA20", "r1": 2.0, "r2": 4.0},
        "Long-Term (Months/Years)": {"period": "2y", "interval": "1d", "fast": "SMA50", "slow": "SMA200", "r1": 2.5, "r2": 5.0}
    }
    
    cfg = style_configs[style_name]
    data = yf.download(ticker_symbol, period=cfg["period"], interval=cfg["interval"], progress=False)
    
    if data.empty:
        return None, None, None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # Technical Indicators
    data["SMA5"] = data["Close"].rolling(5).mean()
    data["SMA20"] = data["Close"].rolling(20).mean()
    data["SMA50"] = data["Close"].rolling(50).mean()
    data["SMA200"] = data["Close"].rolling(200).mean()
    data["EMA9"] = data["Close"].ewm(span=9, adjust=False).mean()
    data["EMA21"] = data["Close"].ewm(span=21, adjust=False).mean()

    typical_price = (data["High"] + data["Low"] + data["Close"]) / 3
    data["VWAP"] = (typical_price * data["Volume"]).cumsum() / data["Volume"].cumsum()

    high_low = data["High"] - data["Low"]
    high_prev_close = (data["High"] - data["Close"].shift(1)).abs()
    low_prev_close = (data["Low"] - data["Close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    data["ATR"] = tr.rolling(14).mean()

    delta = data["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    data["RSI"] = 100 - (100 / (1 + rs))

    fast_ma, slow_ma = cfg["fast"], cfg["slow"]
    if style_name == "Long-Term (Months/Years)" and data["SMA200"].dropna().empty:
        fast_ma, slow_ma = "SMA20", "SMA50"

    clean_data = data.dropna(subset=[fast_ma, slow_ma, "RSI"]).copy()
    if clean_data.empty or len(clean_data) < 2:
        return None, None, None

    latest_bar = clean_data.iloc[-1]
    prev_bar = clean_data.iloc[-2]
    current_price = float(latest_bar["Close"])
    current_atr = float(latest_bar["ATR"]) if not pd.isna(latest_bar["ATR"]) else current_price * 0.005

    bullish_score, bearish_score = 0, 0
    reasons = []

    # ORB High/Low Check for Scalping
    orb_high, orb_low = None, None
    if "Scalping" in style_name and len(clean_data) >= 15:
        first_15m = clean_data.head(15)
        orb_high = float(first_15m["High"].max())
        orb_low = float(first_15m["Low"].min())
        if current_price > orb_high:
            bullish_score += 2
            reasons.append(f"ORB Breakout (${orb_high:.2f})")
        elif current_price < orb_low:
            bearish_score += 2
            reasons.append(f"ORB Breakdown (${orb_low:.2f})")

    # Options Put/Call Ratio Sentiment
    if pcr_val is not None:
        if pcr_val < 0.6:
            bullish_score += 1
            reasons.append("Call Heavy Sentiment")
        elif pcr_val > 1.2:
            bearish_score += 1
            reasons.append("Put Heavy Sentiment")

    # Cash Flow Sentiment Impact (Higher weight for Swing / Short / Long Term)
    if cf_yield is not None:
        if cf_yield > 0:
            bullish_score += 1
            reasons.append("Positive Cash Generation")
        elif cf_yield < 0:
            bearish_score += 1
            reasons.append("Negative Cash Flow")

    if float(prev_bar[fast_ma]) <= float(prev_bar[slow_ma]) and float(latest_bar[fast_ma]) > float(latest_bar[slow_ma]):
        bullish_score += 2
        reasons.append(f"Cross: {fast_ma} > {slow_ma}")
    elif float(prev_bar[fast_ma]) >= float(prev_bar[slow_ma]) and float(latest_bar[fast_ma]) < float(latest_bar[slow_ma]):
        bearish_score += 2
        reasons.append(f"Cross: {fast_ma} < {slow_ma}")

    if float(latest_bar[fast_ma]) > float(latest_bar[slow_ma]):
        bullish_score += 1
    elif float(latest_bar[fast_ma]) < float(latest_bar[slow_ma]):
        bearish_score += 1

    rsi_val = float(latest_bar["RSI"])
    if rsi_val < 35:
        bullish_score += 1
        reasons.append(f"Oversold RSI ({rsi_val:.1f})")
    elif rsi_val > 65:
        bearish_score += 1
        reasons.append(f"Overbought RSI ({rsi_val:.1f})")

    signal = "BUY" if bullish_score >= bearish_score else "SELL"

    # Stop & Targets
    if "Scalping" in style_name:
        stop_dist = max(current_atr * 1.2, current_price * 0.003)
    else:
        stop_dist = current_price * (risk_percent / 100.0)

    if signal == "BUY":
        entry_p = current_price
        sl_p = entry_p - stop_dist
        t1_p = entry_p + (stop_dist * cfg["r1"])
        t2_p = entry_p + (stop_dist * cfg["r2"])
    else:
        entry_p = current_price
        sl_p = entry_p + stop_dist
        t1_p = entry_p - (stop_dist * cfg["r1"])
        t2_p = entry_p - (stop_dist * cfg["r2"])

    setup_dict = {
        "Style": style_name,
        "Signal": signal,
        "Entry": f"${entry_p:.2f}",
        "Stop Loss": f"${sl_p:.2f}",
        "Target 1": f"${t1_p:.2f}",
        "Target 2": f"${t2_p:.2f}",
        "Options PCR": pcr_sentiment,
        "Cash Flow Sentiment": cf_sentiment,
        "RSI": f"{rsi_val:.1f}",
        "Rationale": ", ".join(reasons) if reasons else "Trend Alignment"
    }

    return setup_dict, clean_data, (orb_high, orb_low)


# SCREENER SELECTION MODE
if navigation_mode == "Scan Top 10 Heavy Volume Movers":
    st.title("🔥 Top 10 Heavy Volume & Momentum Movers Screener")
    st.caption("Scans market movers evaluating RVOL, % Change, Current Volume, Share Float, and ATR(14).")

    with st.spinner("Scanning Top 10 heavy movers..."):
        movers_df = scan_top10_heavy_movers(WATCHLIST_TICKERS)

    if not movers_df.empty:
        display_df = movers_df.copy()
        display_df["Rank"] = range(1, len(display_df) + 1)
        display_df["Price"] = display_df["Price"].map(lambda x: f"${x:.2f}")
        display_df["Change %"] = display_df["Change %"].map(lambda x: f"{x:+.2f}%")
        display_df["Current Volume"] = display_df["Current Volume"].map(lambda x: f"{x:,}")
        display_df["RVOL"] = display_df["RVOL"].map(lambda x: f"{x:.2f}x")
        display_df["ATR (14)"] = display_df["ATR (14)"].map(lambda x: f"${x:.2f}")
        display_df["ATR %"] = display_df["ATR %"].map(lambda x: f"{x:.2f}%")

        display_df = display_df[["Rank", "Ticker", "Price", "Change %", "Current Volume", "RVOL", "ATR (14)", "ATR %", "Share Float"]]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        selected_ticker = st.selectbox(
            "Select one of the Top 10 Heavy Movers for Multi-Style Analysis:",
            movers_df["Ticker"].tolist(),
            index=0
        )
    else:
        st.warning("Could not fetch heavy movers data.")
        selected_ticker = "NVDA"
else:
    st.title("⚡ Manual Stock Signal & Chart Analyzer")
    selected_ticker = st.sidebar.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, PANW):", "PANW")

# Sidebar Controls
focus_style = st.sidebar.selectbox(
    "Select Primary Focus Style for Charting:",
    ["Scalping (15m ORB + 1m)", "Day Trade (Intraday)", "Swing Trade", "Short-Term (1-4 Weeks)", "Long-Term (Months/Years)"]
)
risk_pct = st.sidebar.slider("Stop Loss Risk %", min_value=0.25, max_value=5.0, value=1.5, step=0.25)


# MULTI-STYLE ANALYSIS ENGINE
if selected_ticker:
    clean_sym = selected_ticker.strip().upper()
    
    # Fetch Options PCR & Cash Flow Sentiment
    pcr_val, pcr_sentiment = fetch_put_call_ratio(clean_sym)
    cf_yield, cf_sentiment = fetch_cash_flow_sentiment(clean_sym)

    st.subheader(f"📊 All Trading Style Signals Matrix: {clean_sym}")
    
    col_a, col_b = st.columns(2)
    col_a.info(f"**Options Positioning (PCR):** {pcr_sentiment}")
    col_b.info(f"**Cash Flow Sentiment:** {cf_sentiment}")

    styles_list = [
        "Scalping (15m ORB + 1m)",
        "Day Trade (Intraday)",
        "Swing Trade",
        "Short-Term (1-4 Weeks)",
        "Long-Term (Months/Years)"
    ]

    all_signals = []
    focused_data = None
    focused_orb = (None, None)

    for style in styles_list:
        setup, c_data, orb_range = evaluate_style_signal(clean_sym, style, risk_pct, pcr_val, pcr_sentiment, cf_yield, cf_sentiment)
        if setup:
            all_signals.append(setup)
        if style == focus_style:
            focused_data = c_data
            focused_orb = orb_range

    if all_signals:
        signals_df = pd.DataFrame(all_signals)
        st.dataframe(signals_df[["Style", "Signal", "Entry", "Stop Loss", "Target 1", "Target 2", "Options PCR", "Cash Flow Sentiment", "RSI", "Rationale"]], use_container_width=True, hide_index=True)

    # Render Chart for Selected Focused Style
    if focused_data is not None and not focused_data.empty:
        st.subheader(f"📈 Focused Chart View: {clean_sym} ({focus_style})")

        display_chart_data = focused_data.tail(60)

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=display_chart_data.index,
            open=display_chart_data["Open"],
            high=display_chart_data["High"],
            low=display_chart_data["Low"],
            close=display_chart_data["Close"],
            name="Price Candles"
        ))

        if "EMA9" in display_chart_data.columns and "Scalping" in focus_style:
            fig.add_trace(go.Scatter(x=display_chart_data.index, y=display_chart_data["EMA9"], line=dict(color="blue", width=1.5), name="9-EMA"))
            fig.add_trace(go.Scatter(x=display_chart_data.index, y=display_chart_data["EMA21"], line=dict(color="orange", width=1.5), name="21-EMA"))
            fig.add_trace(go.Scatter(x=display_chart_data.index, y=display_chart_data["VWAP"], line=dict(color="purple", width=1.5, dash="dot"), name="VWAP"))
        else:
            fig.add_trace(go.Scatter(x=display_chart_data.index, y=display_chart_data["SMA5"], line=dict(color="blue", width=1.5), name="5-SMA"))
            fig.add_trace(go.Scatter(x=display_chart_data.index, y=display_chart_data["SMA20"], line=dict(color="orange", width=1.5), name="20-SMA"))

        if focus_style == "Scalping (15m ORB + 1m)" and focused_orb[0] and focused_orb[1]:
            fig.add_hline(y=focused_orb[0], line_dash="solid", line_color="orange", annotation_text=f"15m ORB High (${focused_orb[0]:.2f})", annotation_position="top left")
            fig.add_hline(y=focused_orb[1], line_dash="solid", line_color="orange", annotation_text=f"15m ORB Low (${focused_orb[1]:.2f})", annotation_position="bottom left")

        fig.update_layout(
            title=f"Candlestick Chart ({focus_style}) for {clean_sym}",
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            height=550
        )
        st.plotly_chart(fig, use_container_width=True)
