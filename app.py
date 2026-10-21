import sys
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf


class StockDataFetcher:
    """Handles fetching historical stock data via yfinance."""

    @staticmethod
    def get_data(ticker_symbol: str, period: str = "60d") -> pd.DataFrame:
        """Fetch daily stock data for the given ticker symbol."""
        try:
            print(f"Fetching data for {ticker_symbol.upper()}...")
            stock = yf.Ticker(ticker_symbol)
            df = stock.history(period=period, interval="1d")

            if df.empty:
                raise ValueError(f"No price data found for symbol '{ticker_symbol}'.")

            # Flatten MultiIndex columns if returned by recent yfinance versions
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            return df
        except Exception as e:
            print(f"Error fetching data: {e}")
            sys.exit(1)


class TechnicalAnalyzer:
    """Computes technical indicators and trading signals."""

    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculates 5-day SMA, 20-day SMA, and 14-day RSI."""
        df = df.copy()

        # Simple Moving Averages
        df["SMA5"] = df["Close"].rolling(window=5).mean()
        df["SMA20"] = df["Close"].rolling(window=20).mean()

        # Relative Strength Index (RSI - 14 Days)
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)  # Prevent division by zero
        df["RSI"] = 100 - (100 / (1 + rs))

        return df

    @staticmethod
    def generate_trade_setup(df: pd.DataFrame, risk_percent: float = 2.0) -> dict:
        """Evaluates trend momentum, generates a Buy/Sell signal, and calculates SL/TP targets."""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        current_price = float(latest["Close"])

        # Signal Scoring
        bullish_score, bearish_score = 0, 0
        reasons = []

        # 1. Moving Average Crossover Logic
        if prev["SMA5"] <= prev["SMA20"] and latest["SMA5"] > latest["SMA20"]:
            bullish_score += 2
            reasons.append("Golden Cross: 5-Day SMA crossed above 20-Day SMA.")
        elif prev["SMA5"] >= prev["SMA20"] and latest["SMA5"] < latest["SMA20"]:
            bearish_score += 2
            reasons.append("Death Cross: 5-Day SMA crossed below 20-Day SMA.")

        # 2. RSI Overbought / Oversold
        rsi_val = float(latest["RSI"]) if not pd.isna(latest["RSI"]) else 50.0
        if rsi_val < 35:
            bullish_score += 1
            reasons.append(f"Oversold RSI ({rsi_val:.1f}).")
        elif rsi_val > 65:
            bearish_score += 1
            reasons.append(f"Overbought RSI ({rsi_val:.1f}).")

        # 3. 7-Day Breakout Check
        recent_7d = df.tail(7)
        seven_day_high = float(recent_7d["High"].iloc[:-1].max())
        seven_day_low = float(recent_7d["Low"].iloc[:-1].min())

        if current_price > seven_day_high:
            bullish_score += 1
            reasons.append("Price breakout above 7-day resistance high.")
        elif current_price < seven_day_low:
            bearish_score += 1
            reasons.append("Price breakdown below 7-day support low.")

        # Determine Final Trade Direction
        if bullish_score > bearish_score and bullish_score >= 2:
            direction = "BUY"
        elif bearish_score > bullish_score and bearish_score >= 2:
            direction = "SELL"
        else:
            direction = "NEUTRAL"

        # Calculate Risk / Reward Levels (Risk Amount = Risk % of Current Price)
        risk_amount = current_price * (risk_percent / 100.0)

        if direction == "BUY":
            entry_price = current_price
            stop_loss = entry_price - risk_amount
            target_1 = entry_price + (risk_amount * 1.5)  # 1 : 1.5 Risk-to-Reward
            target_2 = entry_price + (risk_amount * 3.0)  # 1 : 3.0 Risk-to-Reward
        elif direction == "SELL":
            entry_price = current_price
            stop_loss = entry_price + risk_amount
            target_1 = entry_price - (risk_amount * 1.5)
            target_2 = entry_price - (risk_amount * 3.0)
        else:  # Neutral
            entry_price = current_price
            stop_loss = current_price - risk_amount
            target_1 = current_price + (risk_amount * 1.5)
            target_2 = current_price + (risk_amount * 3.0)

        return {
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_1": target_1,
            "target_2": target_2,
            "rsi": rsi_val,
            "reasons": reasons if reasons else ["Consolidation range. No explicit setup."],
        }


class ForecastEngine:
    """Generates hypothetical predictive candles for future projection."""

    @staticmethod
    def generate_forecast_candles(df: pd.DataFrame, direction: str, days: int = 3) -> pd.DataFrame:
        """Projects 3 hypothetical future candles based on trend direction and recent volatility."""
        last_row = df.iloc[-1]
        last_date = last_row.name
        last_close = float(last_row["Close"])

        # Calculate average daily range (volatility) from last 10 days
        recent_ranges = (df["High"].tail(10) - df["Low"].tail(10)) / df["Close"].tail(10)
        avg_volatility = float(recent_ranges.mean()) if not recent_ranges.empty else 0.015

        # Set directional drift factor
        if direction == "BUY":
            drift_pct = 0.008  # Positive bias
        elif direction == "SELL":
            drift_pct = -0.008  # Negative bias
        else:
            drift_pct = 0.001  # Flat bias

        future_candles = []
        current_price = last_close
        current_date = last_date

        for i in range(1, days + 1):
            # Advance to next weekday (skip weekends)
            current_date += timedelta(days=1)
            while current_date.weekday() >= 5:
                current_date += timedelta(days=1)

            expected_move = current_price * drift_pct
            open_p = current_price
            close_p = open_p + expected_move + np.random.normal(0, current_price * avg_volatility * 0.3)
            high_p = max(open_p, close_p) + abs(np.random.normal(0, current_price * avg_volatility * 0.25))
            low_p = min(open_p, close_p) - abs(np.random.normal(0, current_price * avg_volatility * 0.25))

            future_candles.append({
                "Date": current_date,
                "Open": open_p,
                "High": high_p,
                "Low": low_p,
                "Close": close_p,
            })
            current_price = close_p

        forecast_df = pd.DataFrame(future_candles)
        forecast_df.set_index("Date", inplace=True)
        return forecast_df


class ChartVisualizer:
    """Handles rendering interactive Plotly candlestick charts with forecast overlays."""

    @staticmethod
    def plot_chart(df: pd.DataFrame, forecast_df: pd.DataFrame, setup: dict, ticker: str):
        """Creates an interactive candlestick chart displaying historical data, forecasted candles, and trade target levels."""
        fig = go.Figure()

        # Display last 30 historical candles
        history_display = df.tail(30)

        # 1. Historical Candlesticks
        fig.add_trace(go.Candlestick(
            x=history_display.index,
            open=history_display["Open"],
            high=history_display["High"],
            low=history_display["Low"],
            close=history_display["Close"],
            name="Historical OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ))

        # 2. Predicted Future Candlesticks (3 Days Ahead)
        fig.add_trace(go.Candlestick(
            x=forecast_df.index,
            open=forecast_df["Open"],
            high=forecast_df["High"],
            low=forecast_df["Low"],
            close=forecast_df["Close"],
            name="3-Day Forecast",
            increasing_line_color="rgba(0, 230, 118, 0.65)",
            decreasing_line_color="rgba(255, 61, 0, 0.65)",
            opacity=0.8,
        ))

        # 3. Plot 5-Day and 20-Day Moving Averages
        if "SMA5" in history_display.columns:
            fig.add_trace(go.Scatter(
                x=history_display.index, y=history_display["SMA5"],
                line=dict(color="#29b6f6", width=1.5), name="5-Day SMA"
            ))
        if "SMA20" in history_display.columns:
            fig.add_trace(go.Scatter(
                x=history_display.index, y=history_display["SMA20"],
                line=dict(color="#ffa726", width=1.5), name="20-Day SMA"
            ))

        # 4. Plot Entry, Stop Loss, and Take Profit Target Lines
        entry = setup["entry_price"]
        sl = setup["stop_loss"]
        t1 = setup["target_1"]
        t2 = setup["target_2"]

        fig.add_hline(y=entry, line_dash="solid", line_color="#ab47bc", annotation_text=f"Entry (${entry:.2f})", annotation_position="top left")
        fig.add_hline(y=sl, line_dash="dash", line_color="#ef5350", annotation_text=f"Stop Loss (${sl:.2f})", annotation_position="bottom right")
        fig.add_hline(y=t1, line_dash="dash", line_color="#81c784", annotation_text=f"Target 1 (${t1:.2f})", annotation_position="top right")
        fig.add_hline(y=t2, line_dash="dash", line_color="#2e7d32", annotation_text=f"Target 2 (${t2:.2f})", annotation_position="top right")

        # 5. Chart Layout Options
        direction_color = "Green" if setup["direction"] == "BUY" else ("Red" if setup["direction"] == "SELL" else "Orange")
        fig.update_layout(
            title=dict(
                text=f"<b>
