import streamlit as st
import pandas as pd
from tradingview_ta import TA_Handler, Interval, Exchange

st.set_page_config(page_title="Quant TradingView Dashboard", layout="wide")

# ==========================================
# WATCHLIST DEFINITIONS
# ==========================================
US_HEAVY_WATCHLIST = ["NVDA", "TSLA", "AMD", "AAPL", "AMZN", "META", "MSFT", "GOOGL", "NFLX", "PLTR", "SPY", "QQQ", "SMCI", "COIN", "MARA", "BA", "BABA", "ARM"]
US_MOMENTUM_WATCHLIST = ["SOUN", "BBAI", "PLUG", "LCID", "RIG", "CLSK", "BITF", "HUT", "DNA", "RXRX", "IONQ", "LAZR", "NIO", "RUN", "TELL", "SOFI", "RBLX", "SNAP", "OPEN", "NOK", "RPD"]
CA_MOMENTUM_WATCHLIST = ["BTE.TO", "LUN.TO", "ATH.TO", "CVE.TO", "ARX.TO", "DML.TO", "FM.TO", "TLG.TO", "HBM.TO", "SU.TO", "WCP.TO", "MEG.TO", "CCO.TO", "POW.TO"]

# ==========================================
# NAVIGATION & SIDEBAR CONTROLS
# ==========================================
st.sidebar.title("🎯 Control Panel")

navigation_mode = st.sidebar.radio(
    "Navigation Mode",
    [
        "Scan Top 10 Heavy Volume Movers",
        "Scan $5–$100 Momentum Stocks (US & CA)",
        "Manual Ticker Entry"
    ]
)

trading_style = st.sidebar.selectbox(
    "Trading Strategy & Timeframe",
    [
        "Scalping (1m - Rapid Execution)",
        "Day Trading (5m Intraday)",
        "Swing Trading (15m/1h Trend)",
        "Long Term (1D Regime/Macro)"
    ]
)

risk_pct = st.sidebar.slider("Stop Loss Risk Selector (%)", min_value=0.25, max_value=5.0, value=1.5, step=0.25)

# ==========================================
# RESILIENT TRADINGVIEW DATA ENGINE
# ==========================================
def fetch_tv_analysis(symbol, interval=Interval.INTERVAL_1_MINUTE):
    """Dynamically checks across exchanges (NASDAQ, NYSE, AMEX, TSX, TSXV) to ensure reliable retrieval."""
    clean_sym = symbol.replace(".TO", "").strip().upper()
    
    if ".TO" in symbol:
        exchanges_to_check = [("canada", "TSX"), ("canada", "TSXV")]
    else:
        exchanges_to_check = [("america", "NASDAQ"), ("america", "NYSE"), ("america", "AMEX")]

    for screener, exchange in exchanges_to_check:
        try:
            handler = TA_Handler(
                symbol=clean_sym,
                screener=screener,
                exchange=exchange,
                interval=interval
            )
            analysis = handler.get_analysis()
            if analysis and hasattr(analysis, 'indicators') and analysis.indicators:
                return analysis, exchange
        except Exception:
            continue

    return None, None

def render_tradingview_widget(symbol="AMD", exchange="NASDAQ", interval_code="1"):
    """Embeds TradingView's interactive chart widget using verified exchange."""
    clean_sym = symbol.replace(".TO", "").strip().upper()
    tv_symbol = f"{exchange}:{clean_sym}"

    tradingview_html = f"""
    <div class="tradingview-widget-container" style="height:550px;width:100%">
      <div id="tradingview_chart" style="height:calc(100% - 32px);width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{tv_symbol}",
        "interval": "{interval_code}",
        "timezone": "America/New_York",
        "theme": "light",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    st.iframe(tradingview_html, height=560)

# ==========================================
# ADVANCED QUANT & PINE SCRIPT SYNTHESIS
# ==========================================
def evaluate_quant_setup(ticker_symbol, style_name, risk_tolerance):
    interval_map = {
        "Scalping (1m - Rapid Execution)": (Interval.INTERVAL_1_MINUTE, "1"),
        "Day Trading (5m Intraday)": (Interval.INTERVAL_5_MINUTES, "5"),
        "Swing Trading (15m/1h Trend)": (Interval.INTERVAL_15_MINUTES, "15"),
        "Long Term (1D Regime/Macro)": (Interval.INTERVAL_1_DAY, "D")
    }

    tv_interval, tv_code = interval_map[style_name]
    analysis, active_exchange = fetch_tv_analysis(ticker_symbol, interval=tv_interval)

    if not analysis:
        return None, tv_code, None

    inds = analysis.indicators
    summary = analysis.summary

    price = float(inds.get("close", 0.0))
    open_price = float(inds.get("open", price))
    high_price = float(inds.get("high", price))
    low_price = float(inds.get("low", price))

    rsi = float(inds.get("RSI", 50.0))
    macd_val = float(inds.get("MACD.macd", 0.0))
    macd_signal = float(inds.get("MACD.signal", 0.0))
    ema20 = float(inds.get("EMA20", price))
    bb_upper = float(inds.get("BB.upper", price * 1.02))
    bb_lower = float(inds.get("BB.lower", price * 0.98))
    ichimoku_base = float(inds.get("Ichimoku.BLine", price))

    tv_rec = summary.get("RECOMMENDATION", "NEUTRAL")
    signal_direction = "BUY" if "BUY" in tv_rec else ("SELL" if "SELL" in tv_rec else "NEUTRAL")

    # Quant Pine Script Approximations
    smc_filter = "Order Block Support (Bullish)" if price <= bb_lower or price <= (low_price * 1.002) else "Order Block Resistance (Bearish)"
    lorentzian_signal = "Bullish Feature Cluster" if (rsi < 60 and macd_val > macd_signal and "BUY" in tv_rec) else "Bearish Feature Cluster"
    hull_trend = "Green Hull Alignment" if price > ema20 else "Red Hull Breakdown"

    # Stop & Target Calculation
    stop_distance = price * (risk_tolerance / 100.0)

    if signal_direction == "BUY":
        entry_price = price
        stop_loss = entry_price - stop_distance
        target_1 = entry_price + (stop_distance * 1.5)
        target_2 = entry_price + (stop_distance * 3.0)
        targets_reached = high_price >= target_2
    else:
        entry_price = price
        stop_loss = entry_price + stop_distance
        target_1 = entry_price - (stop_distance * 1.5)
        target_2 = entry_price - (stop_distance * 3.0)
        targets_reached = low_price <= target_2

    quant_data = {
        "Ticker": ticker_symbol,
        "Exchange": active_exchange,
        "Signal": signal_direction,
        "Price": price,
        "Entry": entry_price,
        "Stop Loss": stop_loss,
        "Target 1": target_1,
        "Target 2": target_2,
        "Targets Reached": targets_reached,
        "RSI": rsi,
        "MACD State": "Bullish Crossover" if macd_val > macd_signal else "Bearish Pressure",
        "Supertrend / BB": "Upper Band Breakout" if price > bb_upper else ("Lower Band Oversold" if price < bb_lower else "Consolidation"),
        "Ichimoku Kijun": "Above Base Line" if price > ichimoku_base else "Below Base Line",
        "SMC Structure": smc_filter,
        "Lorentzian Class": lorentzian_signal,
        "Hull Suite": hull_trend
    }

    return quant_data, tv_code, active_exchange

# ==========================================
# SCREENER ENGINE
# ==========================================
@st.cache_data(ttl=180)
def scan_tickers(ticker_list, min_price=0.0, max_price=10000.0):
    results = []
    for sym in ticker_list:
        try:
            analysis, exchange = fetch_tv_analysis(sym, interval=Interval.INTERVAL_1_DAY)
            if not analysis:
                continue
            inds = analysis.indicators
            price = float(inds.get("close", 0.0))
            if price < min_price or price > max_price:
                continue
            
            change = float(inds.get("change", 0.0))
            volume = int(inds.get("volume", 0))
            atr = float(inds.get("Volatility.D", price * 0.02))

            results.append({
                "Ticker": sym,
                "Exchange": exchange,
                "Price": price,
                "Change %": change,
                "Volume": volume,
                "ATR": atr,
                "Score": abs(change) * (volume / 1e6)
            })
        except Exception:
            continue

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by="Score", ascending=False).head(10).reset_index(drop=True)
    return df

# ==========================================
# MAIN DASHBOARD ROUTING
# ==========================================
if navigation_mode == "Scan Top 10 Heavy Volume Movers":
    st.title("🔥 Top 10 Heavy Volume Movers (TradingView Scanner)")
    movers_df = scan_tickers(US_HEAVY_WATCHLIST)
    
    if not movers_df.empty:
        disp = movers_df.copy()
        disp["Price"] = disp["Price"].map(lambda x: f"${x:.2f}")
        disp["Change %"] = disp["Change %"].map(lambda x: f"{x:+.2f}%")
        disp["Volume"] = disp["Volume"].map(lambda x: f"{x:,}")
        disp["ATR"] = disp["ATR"].map(lambda x: f"${x:.2f}")
        st.dataframe(disp[["Ticker", "Exchange", "Price", "Change %", "Volume", "ATR"]], width="stretch", hide_index=True)
        selected_ticker = st.selectbox("Select Ticker for Quant Deep Dive:", movers_df["Ticker"].tolist())
    else:
        selected_ticker = "NVDA"

elif navigation_mode == "Scan $5–$100 Momentum Stocks (US & CA)":
    st.title("💎 $5–$100 High Momentum Screener (US & CA)")
    market_choice = st.radio("Target Market", ["US Market (NYSE/NASDAQ)", "Canadian Market (TSX/TSXV)"], horizontal=True)
    
    watchlist = US_MOMENTUM_WATCHLIST if "US" in market_choice else CA_MOMENTUM_WATCHLIST
    movers_df = scan_tickers(watchlist, min_price=5.0, max_price=100.0)

    if not movers_df.empty:
        disp = movers_df.copy()
        disp["Price"] = disp["Price"].map(lambda x: f"${x:.2f}")
        disp["Change %"] = disp["Change %"].map(lambda x: f"{x:+.2f}%")
        disp["Volume"] = disp["Volume"].map(lambda x: f"{x:,}")
        st.dataframe(disp[["Ticker", "Exchange", "Price", "Change %", "Volume"]], width="stretch", hide_index=True)
        selected_ticker = st.selectbox("Select Ticker for Quant Deep Dive:", movers_df["Ticker"].tolist())
    else:
        selected_ticker = "SOUN"

else:
    st.title("⚡ Manual Ticker Quant Analyzer")
    selected_ticker = st.text_input("Enter Ticker Symbol (e.g. NVDA, AMD, TSLA, SU.TO):", "NVDA").strip().upper()

# ==========================================
# QUANT ANALYSIS DISPLAY ENGINE
# ==========================================
if selected_ticker:
    quant_setup, tv_code, active_exchange = evaluate_quant_setup(selected_ticker, trading_style, risk_pct)

    if quant_setup:
        st.subheader(f"📊 Quantitative Indicator & Script Analysis: {selected_ticker} ({active_exchange})")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Price", f"${quant_setup['Price']:.2f}")
        col2.metric("RSI (14)", f"{quant_setup['RSI']:.1f}")
        col3.metric("TradingView Regime", quant_setup['Signal'])
        col4.metric("Risk Percent", f"{risk_pct}%")

        script_df = pd.DataFrame([{
            "Lorentzian Classification": quant_setup["Lorentzian Class"],
            "Smart Money Concepts (SMC)": quant_setup["SMC Structure"],
            "Hull Suite Trend": quant_setup["Hull Suite"],
            "MACD State": quant_setup["MACD State"],
            "Supertrend / Bollinger": quant_setup["Supertrend / BB"],
            "Ichimoku Kijun Alignment": quant_setup["Ichimoku Kijun"]
        }])
        st.dataframe(script_df, width="stretch", hide_index=True)

        st.subheader("🎯 Optimal Trade Setup Execution")

        if quant_setup["Targets Reached"]:
            st.info(f"🚫 **Trade Setup Suppressed for {selected_ticker}:** The primary intraday profit targets (Target 1 / Target 2) have already been reached during this session. No new execution parameters generated.")
        else:
            trade_cols = st.columns(5)
            trade_cols[0].metric("Suggested Action", quant_setup["Signal"])
            trade_cols[1].metric("Ideal Entry", f"${quant_setup['Entry']:.2f}")
            trade_cols[2].metric("Stop Loss", f"${quant_setup['Stop Loss']:.2f}")
            trade_cols[3].metric("Target 1 (1.5x Risk)", f"${quant_setup['Target 1']:.2f}")
            trade_cols[4].metric("Target 2 (3.0x Risk)", f"${quant_setup['Target 2']:.2f}")

        st.subheader(f"📈 Real-Time TradingView Interactive Chart: {selected_ticker}")
        render_tradingview_widget(selected_ticker, exchange=active_exchange, interval_code=tv_code)
    else:
        st.error(f"Could not load TradingView analysis for symbol: {selected_ticker}. Check ticker spelling or exchange listing.")
