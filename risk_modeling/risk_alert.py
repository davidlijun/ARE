import warnings
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.stats import linregress

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)


def calculate_hurst(prices, volumes=None):
    """Measures Persistence: > 0.5 is Trending, < 0.5 is Mean Reverting.

    If volumes are provided, the function weights price changes by volume to
    avoid low-volume squeezes distorting the Hurst estimate.
    """
    prices = np.asarray(prices, dtype=np.float64)

    def _hurst_from_series(ts):
        if len(ts) < 20 or np.all(ts == ts[0]):
            return np.nan
        max_lag = min(20, len(ts) - 1)
        lags = range(2, max_lag)
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        if np.any(np.array(tau) <= 0):
            return np.nan
        reg = linregress(np.log(lags), np.log(tau))
        return reg.slope * 2.0

    if volumes is not None:
        volumes = np.asarray(volumes, dtype=np.float64)
        if len(prices) == len(volumes) and len(prices) >= 21:
            price_diff = np.diff(prices)
            volume_slice = volumes[1:len(price_diff) + 1]
            if len(price_diff) == len(volume_slice) and not np.all(volume_slice == 0):
                vw_returns = price_diff * volume_slice
                hurst_vw = _hurst_from_series(vw_returns)
                if not np.isnan(hurst_vw):
                    return hurst_vw
        # Fall back to raw price Hurst if volume weighting fails
    return _hurst_from_series(prices)

def calculate_tail_index(returns):
    """Measures Risk: < 1.6 is 'Fat Tail' (High Risk of Crash)"""
    abs_returns = np.sort(np.abs(returns))
    if len(abs_returns) < 5:
        return np.nan
    k = max(1, int(len(abs_returns) * 0.05))  # Look at top 5% extremes
    tails = abs_returns[-k:]
    if tails[0] <= 0:
        return np.nan
    return 1 / (np.mean(np.log(tails / tails[0])))


def scan_now(ticker_symbol="QQQ"):
    print(f"--- Scanning {ticker_symbol} Mandelbrot Status ---")
    
    # 1. Get Data (Daily for long term, 5-min for immediate trend)
    data = yf.download(ticker_symbol, period="1mo", interval="5m")
    daily_data = yf.download(ticker_symbol, period="2y", interval="1d")
    
    # 2. Process Returns
    if daily_data.empty or data.empty:
        print("Error: insufficient market data returned from yfinance.")
        return

    daily_returns = daily_data['Close'].pct_change().dropna().values
    intraday_prices = data['Close'].dropna().values
    intraday_volumes = data['Volume'].dropna().values
    if len(intraday_prices) == 0 or len(intraday_volumes) == 0:
        print("Error: no intraday price or volume data available.")
        return

    last_price = intraday_prices[-1]
    if hasattr(last_price, 'item'):
        last_price = float(last_price.item())
    else:
        last_price = float(last_price)

    # 3. Calculate Indicators
    h_intraday = calculate_hurst(intraday_prices[-100:], intraday_volumes[-100:])
    alpha = calculate_tail_index(daily_returns)         # Long term risk
    
    # 4. Classify Regime
    regime = "UNKNOWN"
    if h_intraday > 0.55 and alpha > 1.7:
        regime = "1 - BULLISH PERSISTENCE (Trend is Real)"
    elif h_intraday < 0.45:
        regime = "4 - UNSTABLE (Mean Reverting/Choppy)"
    elif alpha < 1.55:
        regime = "5 - TAIL RISK (Danger of Sudden Move)"
    else:
        regime = "3 - NEUTRAL / RANDOM WALK"

    # 5. Output Results
    print(f"Current Price:  {last_price:.2f}")
    print(f"Hurst (Trend):  {np.nan if np.isnan(h_intraday) else h_intraday:.3f}")
    print(f"Tail Index:     {np.nan if np.isnan(alpha) else alpha:.3f}")
    print(f"RESULT REGIME:  {regime}")
    print("-" * 40)

if __name__ == "__main__":
    scan_now("QQQ")
    scan_now("SPY")
    