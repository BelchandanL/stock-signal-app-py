import streamlit as st
import pandas as pd
from tradingview_screener import Query, col
from tradingview_ta import TA_Handler, Interval

st.set_page_config(page_title="Multi-Exchange All-Industry Quant Dashboard", layout="wide")

# ==========================================
# NAVIGATION & SIDEBAR CONTROLS
# ==========================================
st.sidebar.title("🎯 Control Panel")

navigation_mode = st.sidebar.radio(
    "Navigation Mode",
    [
        "Scan Top Heavy Movers (All North American Exchanges)",
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
# MULTI-EXCHANGE & MULTI-INDUSTRY SCANNER
# ==========================================
@st.cache_data(ttl=60)
def scan_all_exchanges(markets=["america", "canada"], min_price=1.0, max_price=10000.0, limit=10):
    """
    Queries TradingView backend across both US (NASDAQ, NYSE, AMEX) and Canadian (TSX, TSXV) markets.
    Combines results and sorts by liquid market activity across all industries.
    """
    combined_results = []

    for m in markets:
        for vol_min in [100000, 50000, 10000]:
            try:
                q = (
                    Query()
                    .set_markets(m)
                    .select('name', 'close', 'change', 'volume', 'relative_volume_10d_calc')
                    .where(
                        col('close').between(min_price, max_price),
                        col('volume') > vol_min
                    )
                    .order_by('volume', ascending=False)
                    .limit(limit)
                )
                data = q.get_scanner_data()
                
                if data is not None and len(data) == 2 and not data[1].empty:
                    df = data[1]
                    for _, row in df.iterrows():
                        raw_ticker = str(row.get('ticker', row.get('name', ''))).strip().upper()
                        
                        if ":" in raw_ticker:
                            detected_exch, pure_sym = raw_ticker.split(":", 1)
                        else:
                            detected_exch = "NASDAQ" if m == "america" else "TSX"
                            pure_sym = raw_ticker

                        clean_sym = pure_sym.replace(".TO", "").replace(".V", "").strip()
                        clean_exch = detected_exch.strip()

                        combined_results.append({
                            "Ticker": clean_sym,
                            "Exchange": clean_exch,
                            "Price": float(row.get('close', 0.0)),
                            "Change %": float(row.get('change', 0.0)),
                            "Volume": int(row.get('volume', 0)),
                            "RVOL": float(row.get('relative_volume_10d_calc', 1.0))
                        })
                    break  # Break threshold loop if query succeeds for this market
            except Exception:
                continue

    if combined_results:
        res_df = pd.DataFrame(combined_results)
        # Deduplicate and sort by Volume across combined market payloads
        res_df = res_df.drop_duplicates(subset=["Ticker", "Exchange"]).sort_values(by="Volume", ascending=False)
        return res_df.head(limit)

    return pd.DataFrame()

def fetch_single_tv_analysis(symbol, interval=Interval.INTERVAL_1_MINUTE, preferred_exchange=None):
    """
    Dynamic Multi-Exchange Resolver.
    Checks NASDAQ, NYSE, AMEX, TSX, TSXV, and OTC dynamically without hardcoded assumptions.
    """
    clean_sym = symbol.split(":")[-1].replace(".TO", "").replace(".V", "").strip().upper()
    is_ca = ".TO" in symbol or symbol.endswith(".V") or preferred_exchange in ["TSX", "TSXV"]
    
    exchanges_to_try = []
    if preferred_exchange and preferred_exchange != "AUTO":
        screener_key = "canada" if preferred_exchange in ["TSX", "TSXV"] else "america"
        exchanges_to_try.append((screener_key, preferred_exchange))
    
    if is_ca:
        exchanges_to_try.extend([("canada", "TSX"), ("canada", "TSXV")])
    else:
        exchanges_to_try.extend([("america", "NASDAQ"), ("america", "NYSE"), ("america", "AMEX"), ("america", "OTC")])

    # Deduplicate sweep list
    seen = set()
    deduped_exchanges = []
    for item in exchanges_to_try:
        if item not in seen:
            seen.add(item)
            deduped_exchanges.append(item)

    for screener, exch in deduped_exchanges:
        try:
            handler = TA_Handler(
                symbol=clean_sym,
                screener=screener,
                exchange=exch,
                interval=interval
            )
            analysis = handler.get_analysis()
            if analysis and hasattr(analysis, "indicators") and analysis.indicators:
                return analysis, exch, clean_sym
        except Exception:
            continue

    # Synthetic Analysis Fallback
    try:
        screener_key = "canada" if is_ca else "america"
        q = Query().set_markets(screener_key).select(
            'close', 'high', 'low', 'RSI', 'MACD.macd', 'MACD.signal', 
            'EMA20', 'SMA50', 'SMA200', 'BB.upper', 'BB.lower', 'Stoch.K', 'Stoch.D'
        ).where(col('name') == clean_sym)
        _, df = q.get_scanner_data()
        if df is not None and not df.empty:
            row = df.iloc[0]
            class SyntheticAnalysis:
                indicators = {
                    "close": float(row.get('close', 1.0)),
                    "high": float(row.get('high', 1.05)),
                    "low": float(row.get('low', 0.95)),
                    "RSI": float(row.get('RSI', 50.0)),
                    "MACD.macd": float(row.get('MACD.macd', 0.1)),
                    "MACD.signal": float(row.get('MACD.signal', 0.05)),
                    "EMA20": float(row.get('EMA20', 1.0)),
                    "SMA50": float(row.get('SMA50', 1.0)),
                    "SMA200": float(row.get('SMA200', 1.0)),
                    "BB.upper": float(row.get('BB.upper', 1.02)),
                    "BB.lower": float(row.get('BB.lower', 0.98)),
                    "Stoch.K": float(row.get('Stoch.K', 50.0)),
                    "Stoch.D": float(row.get('Stoch.D', 50.0))
                }
                summary = {"RECOMMENDATION": "BUY" if float(row.get('RSI', 50)) > 50 else "SELL"}
            default_exch = preferred_exchange if preferred_exchange else ("TSX" if is_ca else "NASDAQ")
            return SyntheticAnalysis(), default_exch, clean_sym
    except Exception:
        pass

    default_exch = preferred_exchange if preferred_exchange else ("TSX" if is_ca else "NASDAQ")
    return None, default_exch, clean_sym

def render_tradingview_widget(symbol, exchange, interval_code="1"):
    """
    Renders TradingView's official interactive chart widget using the dynamically detected exchange.
    """
    clean_sym = symbol.split(":")[-1].replace(".TO", "").replace(".V", "").strip().upper()
    clean_exch = str(exchange).strip().upper() if exchange else "NASDAQ"
    
    tv_symbol = f"{clean_exch}:{clean_sym}"

    tradingview_html = f"""
    <div class="tradingview-widget-container" style="height:580px;width:100%">
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
        "details": true,
        "hotlist": true,
        "calendar": true,
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    st.iframe(tradingview_html, height=590)

# ==========================================
# 7-INDICATOR QUANT ENGINE
# ==========================================
def evaluate_quant_setup(ticker_symbol, style_name, risk_tolerance, preferred_exchange=None):
    interval_map = {
        "Scalping (1m - Rapid Execution)": (Interval.INTERVAL_1_MINUTE, "1"),
        "Day Trading (5m Intraday)": (Interval.INTERVAL_5_MINUTES, "5"),
        "Swing Trading (15m/1h Trend)": (Interval.INTERVAL_15_MINUTES, "15"),
        "Long Term (1D Regime/Macro)": (Interval.INTERVAL_1_DAY, "D")
    }

    tv_interval, tv_code = interval_map[style_name]
    analysis, active_exchange, clean_symbol = fetch_single_tv_analysis(
        ticker_symbol, 
        interval=tv_interval, 
        preferred_exchange=preferred_exchange
    )

    if not analysis:
        return None, tv_code, active_exchange, clean_symbol

    inds = analysis.indicators if hasattr(analysis, "indicators") and analysis.indicators else {}
    summary = analysis.summary if hasattr(analysis, "summary") and analysis.summary else {}

    price = float(inds.get("close", 0.0))
    high = float(inds.get("high", price * 1.02 if price > 0 else 0.01))
    low = float(inds.get("low", price * 0.98 if price > 0 else 0.01))

    # 1. RSI (14)
    rsi = float(inds.get("RSI", 50.0))
    rsi_state = "Oversold (<30)" if rsi <= 30 else ("Overbought (>70)" if rsi >= 70 else f"Neutral ({rsi:.1f})")

    # 2. Moving Averages
    ema20 = float(inds.get("EMA20", price))
    sma50 = float(inds.get("SMA50", price))
    ma_trend = "Strong Uptrend (Price > EMA20 > SMA50)" if price > ema20 > sma50 else ("Downtrend Alignment" if price < ema20 else "Consolidation Range")

    # 3. MACD
    macd_val = float(inds.get("MACD.macd", 0.0))
    macd_signal = float(inds.get("MACD.signal", 0.0))
    macd_state = "Bullish Crossover" if macd_val > macd_signal else "Bearish Momentum"

    # 4. Bollinger Bands
    bb_upper = float(inds.get("BB.upper", price * 1.02 if price > 0 else 0.01))
    bb_lower = float(inds.get("BB.lower", price * 0.98 if price > 0 else 0.01))
    bb_pos = "Upper Band Squeeze" if price >= bb_upper else ("Lower Band Dip" if price <= bb_lower else "Mid-Band Channel")

    # 5. Dynamic Fibonacci Retracement
    diff = max(high - low, 0.0001)
    fib_500 = high - (diff * 0.500)
    fib_618 = high - (diff * 0.618)
    fib_state = f"50.0% Key Level: ${fib_500:.2f} (Golden Pocket: ${fib_618:.2f})"

    # 6. Stochastic Oscillator
    stoch_k = float(inds.get("Stoch.K", 50.0))
    stoch_d = float(inds.get("Stoch.D", 50.0))
    stoch_state = "Bullish Cross (%K > %D)" if stoch_k > stoch_d else "Bearish Cross (%K < %D)"

    # 7. Volume Profile
    vol_profile_poc = (high + low + price) / 3.0
    vol_state = f"POC Node Proxy: ${vol_profile_poc:.2f}"

    # Signals
    tv_rec = str(summary.get("RECOMMENDATION", "NEUTRAL")).upper() if summary else "NEUTRAL"
    if "BUY" in tv_rec:
        signal_direction = "BUY"
    elif "SELL" in tv_rec:
        signal_direction = "SELL"
    else:
        signal_direction = "BUY" if rsi >= 50 else "SELL"

    # Risk Targets
    stop_distance = max(price * (risk_tolerance / 100.0), 0.0001)

    if signal_direction == "BUY":
        entry_price = price
        stop_loss = max(entry_price - stop_distance, 0.0001)
        target_1 = entry_price + (stop_distance * 1.5)
        target_2 = entry_price + (stop_distance * 3.0)
        targets_reached = high >= target_2 and target_2 > 0
    else:
        entry_price = price
        stop_loss = entry_price + stop_distance
        target_1 = max(entry_price - (stop_distance * 1.5), 0.0001)
        target_2 = max(entry_price - (stop_distance * 3.0), 0.0001)
        targets_reached = low <= target_2 and target_2 > 0

    quant_data = {
        "Ticker": clean_symbol,
        "Exchange": active_exchange,
        "Signal": signal_direction,
        "Price": price,
        "Entry": entry_price,
        "Stop Loss": stop_loss,
        "Target 1": target_1,
        "Target 2": target_2,
        "Targets Reached": targets_reached,
        "RSI": rsi_state,
        "MA Alignment": ma_trend,
        "MACD Signal": macd_state,
        "Bollinger Band": bb_pos,
        "Fibonacci Levels": fib_state,
        "Stochastic": stoch_state,
        "Volume Profile POC": vol_state
    }

    return quant_data, tv_code, active_exchange, clean_symbol

# ==========================================
# MAIN DASHBOARD ROUTING
# ==========================================
selected_exchange = None

if navigation_mode == "Scan Top Heavy Movers (All North American Exchanges)":
    st.title("🔥 Top Heavy Volume Movers (NYSE, NASDAQ, AMEX, TSX, TSXV)")
    st.caption("Cross-exchange aggregate scan covering Tech, Industrials, Energy, Financials, and Healthcare.")
    
    movers_df = scan_all_exchanges(markets=["america", "canada"], min_price=1.0, limit=10)
    
    if not movers_df.empty:
        disp = movers_df.copy()
        disp["Price"] = disp["Price"].map(lambda x: f"${x:.2f}")
        disp["Change %"] = disp["Change %"].map(lambda x: f"{x:+.2f}%")
        disp["Volume"] = disp["Volume"].map(lambda x: f"{x:,}")
        disp["RVOL"] = disp["RVOL"].map(lambda x: f"{x:.2f}x")
        st.dataframe(disp[["Ticker", "Exchange", "Price", "Change %", "Volume", "RVOL"]], width="stretch", hide_index=True)
        
        selected_ticker = st.selectbox("Select Ticker for Quant Deep Dive:", movers_df["Ticker"].tolist())
        exchange_lookup = dict(zip(movers_df["Ticker"], movers_df["Exchange"]))
        selected_exchange = exchange_lookup.get(selected_ticker)
    else:
        st.info("Market scanner refreshing... select or enter a ticker below.")
        selected_ticker = "NVDA"
        selected_exchange = "NASDAQ"

elif navigation_mode == "Scan $5–$100 Momentum Stocks (US & CA)":
    st.title("💎 $5–$100 High Momentum Market Screener")
    market_choice = st.radio("Target Market", ["All North American Markets (US & CA)", "US Market Only (NYSE/NASDAQ/AMEX)", "Canadian Market Only (TSX/TSXV)"], horizontal=True)
    
    if "All" in market_choice:
        target_mkts = ["america", "canada"]
    elif "US" in market_choice:
        target_mkts = ["america"]
    else:
        target_mkts = ["canada"]

    movers_df = scan_all_exchanges(markets=target_mkts, min_price=5.0, max_price=100.0, limit=10)

    if not movers_df.empty:
        disp = movers_df.copy()
        disp["Price"] = disp["Price"].map(lambda x: f"${x:.2f}")
        disp["Change %"] = disp["Change %"].map(lambda x: f"{x:+.2f}%")
        disp["Volume"] = disp["Volume"].map(lambda x: f"{x:,}")
        disp["RVOL"] = disp["RVOL"].map(lambda x: f"{x:.2f}x")
        st.dataframe(disp[["Ticker", "Exchange", "Price", "Change %", "Volume", "RVOL"]], width="stretch", hide_index=True)
        
        selected_ticker = st.selectbox("Select Ticker for Quant Deep Dive:", movers_df["Ticker"].tolist())
        exchange_lookup = dict(zip(movers_df["Ticker"], movers_df["Exchange"]))
        selected_exchange = exchange_lookup.get(selected_ticker)
    else:
        st.info("No stocks found matching exact filter criteria right now.")
        selected_ticker = "SOUN"
        selected_exchange = "NASDAQ"

else:
    st.title("⚡ Manual Ticker Quant Analyzer")
    raw_input = st.text_input("Enter Ticker Symbol (e.g. INTC, LABT, PANW, NVDA, AMD, TSLA, SU, BTE, XOM, JPM):", "NVDA").strip().upper()
    selected_ticker = raw_input.split(":")[-1].replace(".TO", "").replace(".V", "").strip()
    selected_exchange = None

# ==========================================
# QUANT ANALYSIS DISPLAY ENGINE
# ==========================================
if selected_ticker:
    quant_setup, tv_code, active_exchange, clean_symbol = evaluate_quant_setup(
        selected_ticker, 
        trading_style, 
        risk_pct, 
        preferred_exchange=selected_exchange
    )

    if quant_setup:
        final_exchange = selected_exchange if selected_exchange else active_exchange
        
        st.subheader(f"📊 7-Indicator Technical Matrix: {clean_symbol} ({final_exchange})")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Price", f"${quant_setup['Price']:.2f}")
        col2.metric("TradingView Signal", quant_setup['Signal'])
        col3.metric("RSI State", quant_setup['RSI'])
        col4.metric("Risk Percent", f"{risk_pct}%")

        # 7 Technical Indicators Output Grid
        script_df = pd.DataFrame([{
            "1. RSI (14)": quant_setup["RSI"],
            "2. Moving Average (EMA/SMA)": quant_setup["MA Alignment"],
            "3. MACD Regime": quant_setup["MACD Signal"],
            "4. Bollinger Bands": quant_setup["Bollinger Band"],
            "5. Fibonacci Retracement": quant_setup["Fibonacci Levels"],
            "6. Stochastic Oscillator": quant_setup["Stochastic"],
            "7. Volume Profile (POC)": quant_setup["Volume Profile POC"]
        }])
        st.dataframe(script_df, width="stretch", hide_index=True)

        st.subheader("🎯 Risk & Target Calculation Engine")

        if quant_setup["Targets Reached"]:
            st.info(f"🚫 **Trade Setup Suppressed for {clean_symbol}:** Profit targets already met during this session.")
        else:
            trade_cols = st.columns(5)
            trade_cols[0].metric("Action", quant_setup["Signal"])
            trade_cols[1].metric("Ideal Entry", f"${quant_setup['Entry']:.2f}")
            trade_cols[2].metric("Stop Loss", f"${quant_setup['Stop Loss']:.2f}")
            trade_cols[3].metric("Target 1 (1.5x Risk)", f"${quant_setup['Target 1']:.2f}")
            trade_cols[4].metric("Target 2 (3.0x Risk)", f"${quant_setup['Target 2']:.2f}")

        st.subheader(f"📈 Real-Time Interactive Chart: {clean_symbol}")
        render_tradingview_widget(clean_symbol, exchange=final_exchange, interval_code=tv_code)
    else:
        st.error(f"Could not load TradingView analysis for symbol: {selected_ticker}. Please verify the ticker symbol.")
