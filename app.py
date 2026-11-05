import streamlit as st
import pandas as pd
from tradingview_screener import Query, col
from tradingview_ta import TA_Handler, Interval

st.set_page_config(page_title="Quant TradingView Market Screener", layout="wide")

# ==========================================
# NAVIGATION & SIDEBAR CONTROLS
# ==========================================
st.sidebar.title("🎯 Control Panel")

navigation_mode = st.sidebar.radio(
    "Navigation Mode",
    [
        "Scan Top 10 Heavy Volume Movers (All US Market)",
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
# DYNAMIC MARKET-WIDE SCANNER ENGINE
# ==========================================
@st.cache_data(ttl=120)
def scan_live_market(market="america", min_price=0.0, max_price=10000.0, limit=10):
    """
    Queries TradingView's backend scanner across the entire market dynamically.
    Extracts the exact exchange directly for chart rendering.
    """
    try:
        q = (
            Query()
            .set_markets(market)
            .select('name', 'close', 'change', 'volume', 'relative_volume_10d_calc')
            .where(
                col('close').between(min_price, max_price),
                col('volume') > 500000
            )
            .order_by('volume', ascending=False)
            .limit(limit)
        )
        data = q.get_scanner_data()
        
        if data is not None and len(data) == 2 and not data[1].empty:
            df = data[1]
            results = []
            for _, row in df.iterrows():
                ticker_full = str(row.get('ticker', ''))
                if ":" in ticker_full:
                    exchange, sym = ticker_full.split(":", 1)
                else:
                    exchange, sym = ("NASDAQ" if market == "america" else "TSX"), ticker_full

                results.append({
                    "Ticker": sym,
                    "Exchange": exchange,
                    "Full_TV_Key": f"{exchange}:{sym}",
                    "Price": float(row.get('close', 0.0)),
                    "Change %": float(row.get('change', 0.0)),
                    "Volume": int(row.get('volume', 0)),
                    "RVOL": float(row.get('relative_volume_10d_calc', 1.0))
                })
            return pd.DataFrame(results)
    except Exception as e:
        st.warning(f"Live Market Query Note: {e}")
    
    return pd.DataFrame()

def fetch_single_tv_analysis(symbol, interval=Interval.INTERVAL_1_MINUTE):
    """
    Reliable single-ticker lookup for manual entry and deep dives.
    Sweeps exchanges (NASDAQ, NYSE, AMEX, TSX, TSXV) until valid indicator data is retrieved.
    """
    clean_sym = symbol.replace(".TO", "").strip().upper()
    is_ca = ".TO" in symbol or symbol.endswith(".V")
    
    if is_ca:
        exchanges_to_try = [("canada", "TSX"), ("canada", "TSXV")]
    else:
        exchanges_to_try = [("america", "NASDAQ"), ("america", "NYSE"), ("america", "AMEX")]

    for screener, exch in exchanges_to_try:
        try:
            handler = TA_Handler(
                symbol=clean_sym,
                screener=screener,
                exchange=exch,
                interval=interval
            )
            analysis = handler.get_analysis()
            if analysis and hasattr(analysis, "indicators") and analysis.indicators:
                return analysis, exch
        except Exception:
            continue

    return None, "NASDAQ" if not is_ca else "TSX"

def render_tradingview_widget(symbol="AMD", exchange="NASDAQ", interval_code="1"):
    """Renders TradingView's interactive chart widget using the verified exchange."""
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
    analysis, active_exchange = fetch_single_tv_analysis(ticker_symbol, interval=tv_interval)

    if not analysis:
        return None, tv_code, active_exchange

    inds = analysis.indicators
    summary = analysis.summary

    price = float(inds.get("close", 0.0))
    high_price = float(inds.get("high", price))
    low_price = float(inds.get("low", price))

    rsi = float(inds.get("RSI", 50.0))
    macd_val = float(inds.get("MACD.macd", 0.0))
    macd_signal = float(inds.get("MACD.signal", 0.0))
    ema20 = float(inds.get("EMA20", price))
    bb_upper = float(inds.get("BB.upper", price * 1.02))
    bb_lower = float(inds.get("BB.lower", price * 0.98))
    ichimoku_base = float(inds.get("Ichimoku.BLine", price))

    tv_rec = summary.get("RECOMMENDATION", "NEUTRAL") if summary else "NEUTRAL"
    signal_direction = "BUY" if "BUY" in tv_rec else ("SELL" if "SELL" in tv_rec else "NEUTRAL")

    # Quant Pine Script Logic Approximations
    smc_filter = "Order Block Support (Bullish)" if price <= bb_lower or price <= (low_price * 1.002) else "Order Block Resistance (Bearish)"
    lorentzian_signal = "Bullish Feature Cluster" if (rsi < 60 and macd_val > macd_signal and "BUY" in tv_rec) else "Bearish Feature Cluster"
    hull_trend = "Green Hull Alignment" if price > ema20 else "Red Hull Breakdown"

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
# MAIN DASHBOARD ROUTING
# ==========================================
if navigation_mode == "Scan Top 10 Heavy Volume Movers (All US Market)":
    st.title("🔥 Top 10 Heavy Volume Movers (Dynamic US Market Scan)")
    st.caption("Scans entire US stock market dynamically via TradingView official scanner.")
    
    movers_df = scan_live_market(market="america", limit=10)
    
    if not movers_df.empty:
        disp = movers_df.copy()
        disp["Price"] = disp["Price"].map(lambda x: f"${x:.2f}")
        disp["Change %"] = disp["Change %"].map(lambda x: f"{x:+.2f}%")
        disp["Volume"] = disp["Volume"].map(lambda x: f"{x:,}")
        disp["RVOL"] = disp["RVOL"].map(lambda x: f"{x:.2f}x")
        st.dataframe(disp[["Ticker", "Exchange", "Price", "Change %", "Volume", "RVOL"]], width="stretch", hide_index=True)
        
        # Build selection dict mapping symbol to detected exchange
        selected_ticker = st.selectbox("Select Ticker for Quant Deep Dive:", movers_df["Ticker"].tolist())
        exchange_lookup = dict(zip(movers_df["Ticker"], movers_df["Exchange"]))
        selected_exchange = exchange_lookup.get(selected_ticker, "NASDAQ")
    else:
        st.warning("Scanning market... enter ticker manually below if delayed.")
        selected_ticker = "NVDA"
        selected_exchange = "NASDAQ"

elif navigation_mode == "Scan $5–$100 Momentum Stocks (US & CA)":
    st.title("💎 $5–$100 High Momentum Market Screener")
    market_choice = st.radio("Target Market", ["US Market (NYSE/NASDAQ/AMEX)", "Canadian Market (TSX/TSXV)"], horizontal=True)
    
    tv_market_key = "america" if "US" in market_choice else "canada"
    movers_df = scan_live_market(market=tv_market_key, min_price=5.0, max_price=100.0, limit=10)

    if not movers_df.empty:
        disp = movers_df.copy()
        disp["Price"] = disp["Price"].map(lambda x: f"${x:.2f}")
        disp["Change %"] = disp["Change %"].map(lambda x: f"{x:+.2f}%")
        disp["Volume"] = disp["Volume"].map(lambda x: f"{x:,}")
        disp["RVOL"] = disp["RVOL"].map(lambda x: f"{x:.2f}x")
        st.dataframe(disp[["Ticker", "Exchange", "Price", "Change %", "Volume", "RVOL"]], width="stretch", hide_index=True)
        
        selected_ticker = st.selectbox("Select Ticker for Quant Deep Dive:", movers_df["Ticker"].tolist())
        exchange_lookup = dict(zip(movers_df["Ticker"], movers_df["Exchange"]))
        selected_exchange = exchange_lookup.get(selected_ticker, "NASDAQ")
    else:
        st.warning("No dynamic scan results returned for selected filters.")
        selected_ticker = "SOUN" if "US" in market_choice else "BTE"
        selected_exchange = "NASDAQ" if "US" in market_choice else "TSX"

else:
    st.title("⚡ Manual Ticker Quant Analyzer")
    selected_ticker = st.text_input("Enter Ticker Symbol (e.g. NVDA, AMD, TSLA, SU):", "NVDA").strip().upper()
    selected_exchange = None  # Force dynamic exchange resolution

# ==========================================
# QUANT ANALYSIS DISPLAY ENGINE
# ==========================================
if selected_ticker:
    quant_setup, tv_code, active_exchange = evaluate_quant_setup(selected_ticker, trading_style, risk_pct)

    if quant_setup:
        # Use verified active_exchange if manual or fallback
        final_exchange = active_exchange if active_exchange else selected_exchange
        
        st.subheader(f"📊 Quantitative Indicator & Script Analysis: {selected_ticker} ({final_exchange})")

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
            st.info(f"🚫 **Trade Setup Suppressed for {selected_ticker}:** The primary profit targets (Target 1 / Target 2) have already been met during this session. Execution parameters disabled to prevent chasing.")
        else:
            trade_cols = st.columns(5)
            trade_cols[0].metric("Suggested Action", quant_setup["Signal"])
            trade_cols[1].metric("Ideal Entry", f"${quant_setup['Entry']:.2f}")
            trade_cols[2].metric("Stop Loss", f"${quant_setup['Stop Loss']:.2f}")
            trade_cols[3].metric("Target 1 (1.5x Risk)", f"${quant_setup['Target 1']:.2f}")
            trade_cols[4].metric("Target 2 (3.0x Risk)", f"${quant_setup['Target 2']:.2f}")

        st.subheader(f"📈 Real-Time TradingView Interactive Chart: {selected_ticker}")
        render_tradingview_widget(selected_ticker, exchange=final_exchange, interval_code=tv_code)
    else:
        st.error(f"Could not load TradingView analysis for symbol: {selected_ticker}. Check ticker spelling or exchange listing.")
