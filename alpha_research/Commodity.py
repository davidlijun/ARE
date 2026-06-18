import yfinance as yf
import numpy as np
import pandas as pd

FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]

def load_gold(start="2018-01-01"):
    df = yf.download("GC=F", start=start, auto_adjust=True, prepost=True)
    df.columns = df.columns.droplevel(1)  # Drop multi-index if exists
    df.reset_index(inplace=True)
    return df

def compute_fibonacci(df, lookback=252):
    recent = df.tail(lookback)
    print(recent[["Date", "Close"]].tail())
    swing_low = recent["Close"].min()
    print(f"Swing Low: {swing_low:.2f}")
    swing_high = recent["Close"].max()
    print(f"Swing High: {swing_high:.2f}")

    fibs = {
        f"{int(level*100)}%": swing_high - level * (swing_high - swing_low)
        for level in FIB_LEVELS
    }
    return swing_low, swing_high, fibs

def trend_slope(df, window=60):
    y = df["Close"].tail(window).values
    x = np.arange(len(y))
    return np.polyfit(x, y, 1)[0]


if __name__ == "__main__":
    df = load_gold()
    low, high, fibs = compute_fibonacci(df)
    slope = trend_slope(df)
    
    print(f"Swing Low: {low:.2f}, Swing High: {high:.2f}")
    print("Fibonacci Levels:")
    for label, level in fibs.items():
        print(f"  {label}: {level:.2f}")
    print(f"Trend Slope: {slope:.4f}")