import warnings
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.stats import linregress
import time

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ============================================================================
# CACHING CONFIGURATION
# ============================================================================
_CACHE = {}
_CACHE_TTL = 300  # Cache data for 5 minutes (300 seconds)


def _get_cached_data(ticker_symbol, data_type, period, interval):
    """Retrieve cached data if available and not expired."""
    cache_key = f"{ticker_symbol}_{data_type}_{period}_{interval}"
    if cache_key in _CACHE:
        data, timestamp = _CACHE[cache_key]
        if time.time() - timestamp < _CACHE_TTL:
            return data
    return None


def _set_cached_data(ticker_symbol, data_type, period, interval, data):
    """Store data in cache with current timestamp."""
    cache_key = f"{ticker_symbol}_{data_type}_{period}_{interval}"
    _CACHE[cache_key] = (data, time.time())


# ============================================================================
# MANDELBROT REGIME CLASSIFICATION THRESHOLDS
# ============================================================================
# Hurst exponent interpretation:
#   > 0.5 = Trending (persistent), < 0.5 = Mean-reverting (anti-persistent)
#   0.45-0.55 = Random walk (weak signal)
HURST_BULLISH_MIN = 0.55  # Threshold for bullish persistence
HURST_UNSTABLE_MAX = 0.45  # Threshold for unstable/choppy market

# Tail index interpretation (Hill estimator):
#   > 1.6 = Normal tails (low crash risk), < 1.6 = Fat tails (high crash risk)
#   Lower values indicate higher probability of extreme moves
TAIL_INDEX_SAFE = 1.7   # Threshold for safe tail risk
TAIL_INDEX_RISKY = 1.55  # Threshold for elevated tail risk


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
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag])))
               for lag in lags]
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
    # Try to retrieve from cache first
    data = _get_cached_data(ticker_symbol, "intraday", "1mo", "5m")
    if data is None:
        data = yf.download(ticker_symbol, period="1mo", interval="5m")
        _set_cached_data(ticker_symbol, "intraday", "1mo", "5m", data)

    daily_data = _get_cached_data(ticker_symbol, "daily", "2y", "1d")
    if daily_data is None:
        daily_data = yf.download(ticker_symbol, period="2y", interval="1d")
        _set_cached_data(ticker_symbol, "daily", "2y", "1d", daily_data)

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
    h_intraday = calculate_hurst(
        intraday_prices[-100:], intraday_volumes[-100:])
    alpha = calculate_tail_index(daily_returns)         # Long term risk

    # 4. Classify Regime
    # Mandelbrot framework: classify based on persistence (Hurst) and tail behavior
    regime = "UNKNOWN"
    if np.isnan(h_intraday) or np.isnan(alpha):
        regime = "ERROR - Invalid Indicators"
    elif h_intraday > HURST_BULLISH_MIN and alpha > TAIL_INDEX_SAFE:
        regime = "1 - BULLISH PERSISTENCE (Trend is Real)"
    elif h_intraday < HURST_UNSTABLE_MAX:
        regime = "4 - UNSTABLE (Mean Reverting/Choppy)"
    elif alpha < TAIL_INDEX_RISKY:
        regime = "5 - TAIL RISK (Danger of Sudden Move)"
    else:
        regime = "3 - NEUTRAL / RANDOM WALK"

    # 5. Output Results
    print(f"Current Price:  {last_price:.2f}")
    print(
        f"Hurst (Trend):  {np.nan if np.isnan(h_intraday) else h_intraday:.3f}")
    print(f"Tail Index:     {np.nan if np.isnan(alpha) else alpha:.3f}")
    print(f"RESULT REGIME:  {regime}")
    print("-" * 40)


if __name__ == "__main__":
    scan_now("QQQ")
    # scan_now("SPY")
