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
_CACHE_TTL = 60  # Cache data for 1 minute (60 seconds)


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
    """
    Volume-Weighted Rescaled Range (VW-R/S)
    Higher Hurst = High volume is driving a persistent trend.
    Lower Hurst = Price is moving, but volume is inconsistent (noise).
    This method is more robust to low-volume periods and can help avoid false signals during squeezes.
    """
    if len(prices) < 50:
        return 0.5

    # 1. Calculate Log Returns
    # log(P_t / P_t-1)
    returns = np.log(prices[1:]) - np.log(prices[:-1])
    # print(returns[:5])  # Print first 5 returns for debugging
    # 2. Apply Volume Weighting if available
    if volumes is not None:
        # Align volumes with returns (volumes has same length as prices)
        # We use volumes from index 1 onwards to match the np.diff length
        vols = np.array(volumes[1:])
        avg_vol = np.mean(vols)

        if avg_vol > 0:
            # Scale returns by (Current Volume / Average Volume)
            rel_vol = vols / avg_vol
            # This weights returns by how much volume is above/below average, emphasizing high-volume moves and de-emphasizing low-volume noise.
            data = returns * rel_vol
        else:
            data = returns
    else:
        # If no volume, use standard log returns
        data = returns

    # 2. Optimized Lags: Powers of 2 provide better fractal scaling
    N = len(data)
    lags = [2**i for i in range(4, int(np.log2(N)))]
    if len(lags) < 2:
        return 0.5

    RS = []
    for lag in lags:
        # Split into non-overlapping blocks
        num_blocks = N // lag
        rs_sub = []
        for i in range(num_blocks):
            block = data[i*lag: (i+1)*lag]
            # Rescaled Range Calculation
            diff = block - np.mean(block)
            cum_sum = np.cumsum(diff)
            r = np.max(cum_sum) - np.min(cum_sum)
            s = np.std(block)
            if s > 0:
                rs_sub.append(r / s)
        if rs_sub:
            RS.append(np.mean(rs_sub))

    if len(RS) < 2:
        return 0.5

    # 3. Regression: log(R/S) vs log(n)
    res = linregress(np.log(lags), np.log(RS))
    return res.slope


def calculate_tail_index(returns):
    """Measures Risk: < 1.6 is 'Fat Tail' (High Risk of Crash)"""
    """Ultra-Sensitive Alpha: Focuses on the 'Crash' zone"""
    if len(returns) < 100:
        return 2.0

    # 1. Focus on the absolute returns (Both tails)
    data = np.abs(returns)
    data = np.sort(data)

    # 2. Sensitivity Adjustment: Look at top 2.5% instead of 5%
    # This prevents the 'dilution' you saw in your test (1.95 result)
    k = int(len(data) * 0.025)
    if k < 5:
        k = 5

    tails = data[-k:]
    # Threshold is the value at the start of the tail
    threshold = tails[0]

    if threshold <= 0:
        return 3.0

    # 3. Hill Estimator
    alpha = 1.0 / (np.mean(np.log(tails / threshold)))
    return alpha
