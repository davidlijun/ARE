import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import linregress
from datetime import datetime, timedelta
import pytz

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
# ============================================================================
# 1. PARAMETERS & THRESHOLDS
# ============================================================================
# Hurst: > 0.55 = Trend Memory, < 0.45 = Mean Reversion
HURST_WINDOW = 300            # 5 hours of 1m data
HURST_TREND_MIN = 0.55
HURST_CHOP_MAX = 0.45

# Tail Index: < 1.55 = Wild Randomness (Jump Risk)
TAIL_BLOCK_SIZE = 200         # Robust window for Hill Estimator
TAIL_PERCENTILE = 5
TAIL_MIN_K = 15
TAIL_RISKY = 1.55             # Regime 5 Trigger
TAIL_SAFE = 1.70              # Required for Regime 1/2 stability

# Volatility: For Active vs. Dormant Risk
VOL_LOOKBACK = 30             # 30-minute window for "Current Vol"
VOL_THRESHOLD = 0.0015        # Threshold to define "Active" movement

# ============================================================================
# 2. FRACTAL MATHEMATICS
# ============================================================================


def calculate_hurst_vw(prices: np.ndarray, volumes: np.ndarray, window: int = 300):
    """
    Volume-Weighted Hurst that adapts to Zero-Volume (After-Hours).
    """
    if len(prices) < window:
        return 0.5

    p = prices[-window:]
    v = volumes[-window:]
    returns = np.log(p[1:] / p[:-1])

    # 1. CHECK FOR ZERO VOLUME (After-Hours Fix)
    # If the average volume is near zero, weighting is impossible/useless.
    avg_vol = np.mean(v)

    if avg_vol > 0.0001:
        # We have volume! Use Volume-Weighting logic
        # Add epsilon to v to prevent division by zero in any specific bar
        vol_weights = (v[1:] + 1) / (avg_vol + 1)
        data = returns * vol_weights
    else:
        # NO VOLUME (Pre/Post Market): Use standard log returns
        # This prevents the Hurst from crashing when Yahoo returns 0 volume
        data = returns

    N = len(data)
    lags = np.unique(np.geomspace(10, N//2, num=20).astype(int))

    RS = []
    for lag in lags:
        num_blocks = N // lag
        rs_sub = []
        for i in range(num_blocks):
            block = data[i*lag: (i+1)*lag]
            s = np.std(block)
            if s > 1e-10:
                r = np.max(np.cumsum(block - np.mean(block))) - \
                    np.min(np.cumsum(block - np.mean(block)))
                rs_sub.append(r / s)
        if rs_sub:
            RS.append(np.mean(rs_sub))

    if len(RS) < 5:
        return 0.5
    return linregress(np.log(lags), np.log(RS)).slope


def calculate_tail_index_robust(returns: np.ndarray, lookback: int = 500):
    """
    Asymmetric Hill Estimator (Left-Tail).
    Filters out 'zero-return' noise bars to avoid Gaussian bias.
    """
    # 1. Filter for 'Active' negative returns only
    active_neg = np.abs(returns[(returns < -1e-6)])

    if len(active_neg) < TAIL_MIN_K:
        return 3.0

    subset = active_neg[-lookback:]

    def hill_est(data):
        k = max(int(len(data) * (TAIL_PERCENTILE / 100)), TAIL_MIN_K)
        tails = np.sort(data)[-k:]
        threshold = tails[0]
        if threshold <= 1e-10:
            return 3.0
        return 1.0 / np.mean(np.log(tails / threshold))

    # Rolling window percentile for conservative risk view
    results = [hill_est(subset[i:i+TAIL_BLOCK_SIZE])
               for i in range(0, len(subset)-TAIL_BLOCK_SIZE, 15)]

    return float(np.percentile(results, 15)) if results else 2.5

# ============================================================================
# 3. PERSISTENT DATA CACHE
# ============================================================================


def get_data_persistent(ticker, interval="1m", period="2y"):
    """Bridges the Yahoo 7-day limit for 1m data using local Parquet files."""
    file_path = f"cache_{ticker}_{interval}.csv"
    now = datetime.now(pytz.utc)

    if os.path.exists(file_path):
        local_df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        if local_df.index.tz is None:
            local_df.index = local_df.index.tz_localize('UTC')

        last_ts = local_df.index[-1]
        # Skip update if we ran this in the last 2 mins (intraday) or 12h (daily)
        wait_time = timedelta(
            minutes=2) if interval == "1m" else timedelta(hours=12)
        if now - last_ts < wait_time:
            return local_df

        # Calculate safe start (Yahoo limit for 1m is 7 days per request)
        start_date = max(last_ts, now - timedelta(days=7)
                         ) if interval == "1m" else last_ts
        new_data = yf.download(ticker, start=start_date,
                               interval=interval, prepost=True, progress=False)

        if not new_data.empty:
            if isinstance(new_data.columns, pd.MultiIndex):
                new_data.columns = new_data.columns.get_level_values(0)
            if new_data.index.tz is None:
                new_data.index = new_data.index.tz_localize('UTC')
            combined = pd.concat([local_df, new_data])
            # Drop duplicates (keeping the most recent version of a minute/day)
            combined = combined[~combined.index.duplicated(
                keep='last')].sort_index()
            combined.to_csv(file_path)
            return combined
        # If the update failed, return the previous cache instead of crashing.
        return local_df
    else:
        # First time download
        p = "7d" if interval == "1m" else period
        df = yf.download(ticker, period=p, interval=interval,
                         prepost=True, progress=False)
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.to_csv(file_path)
        return df
# ============================================================================
# NEW JUDGMENT INDICATORS
# ============================================================================


def calculate_shannon_entropy(returns, bins=10):
    """
    Shannon Entropy: Measures Market Complexity.
    Low Entropy (< 2.0) = Highly ordered, Hurst is reliable.
    High Entropy (> 3.0) = Chaotic Noise, Hurst is likely a 'fake'.
    """
    if len(returns) < 50:
        return 0
    # Create probability distribution of returns
    hist, _ = np.histogram(returns, bins=bins, density=True)
    hist = hist[hist > 0]  # Remove zeros for log calculation
    probs = hist / np.sum(hist)
    entropy = -np.sum(probs * np.log2(probs))
    return entropy


def calculate_vpin_lite(returns, volumes, window=50):
    """
    Safe VPIN: Returns 0.5 (Neutral) if volume is missing.
    """
    if len(returns) < window:
        return 0.5
    r = returns[-window:]
    v = volumes[-window:]

    total_vol = np.sum(v)

    # FIX: Check for Zero Volume to avoid NaN
    if total_vol < 1e-9:
        return 0.5  # Return neutral if no volume data exists

    # Estimate Buy/Sell Volume based on price change sign
    buy_vol = np.where(r > 0, v, 0)
    sell_vol = np.where(r < 0, v, 0)

    imbalance = np.abs(buy_vol - sell_vol)
    vpin = np.sum(imbalance) / total_vol
    return vpin


def calculate_cvd_proxy(data_df, window=100):
    """
    Safe CVD: Returns 0 slope if volume is missing.
    """
    df = data_df.tail(window).copy()

    # Check if we have any volume at all
    if df['Volume'].sum() < 1e-9:
        return 0.0, 0.0  # No volume = No delta

    # Standard CVD logic
    midpoint = (df['High'] + df['Low']) / 2
    denominator = (df['High'] - df['Low'] + 1e-10)
    multiplier = ((df['Close'] - df['Low']) -
                  (df['High'] - df['Close'])) / denominator
    delta = multiplier * df['Volume']
    cvd = delta.cumsum()

    cvd_slope = linregress(np.arange(len(cvd)), cvd.values).slope
    return cvd_slope, cvd.iloc[-1]

# ============================================================================
# UPDATED SCANNER WITH JUDGMENT LOGIC
# ============================================================================


def compute_judgment(prices, volumes, data_1m, h_val, alpha):
    returns = np.diff(np.log(prices))
    cvd_slope, _ = calculate_cvd_proxy(data_1m)
    entropy = calculate_shannon_entropy(returns[-200:])
    vpin = calculate_vpin_lite(returns, volumes[-len(returns):])

    judgment = "STABLE"

    if len(prices) >= 10 and prices[-1] < prices[-10] and cvd_slope > 0:
        judgment = "BULLISH ABSORPTION (Institutions are buying the dip)"
    elif len(prices) >= 10 and prices[-1] > prices[-10] and cvd_slope < 0:
        judgment = "BEARISH EXHAUSTION (Retail is chasing, Big Money is exiting)"

    if h_val > 0.60 and entropy > 3.0:
        judgment = "NOISY TREND (Hurst is high but unreliable/chaotic)"

    if vpin > 0.75:
        judgment = "TOXIC FLOW (High probability of a structural Jump soon)"

    return judgment, entropy, vpin, cvd_slope


def scan_with_judgment(ticker):
    return scan_now(ticker, show_judgment=True)

# ============================================================================
# 4. MAIN SCANNER
# ============================================================================


def generate_suggestion(regime, judgment, entropy, alpha, h_val, vpin, cvd_slope):
    """
    Synthesizes all fractal metrics into a concrete action.
    """
    # 1. CRITICAL RISK CHECK (Regime 5 or Toxic Flow)
    if "5 - TAIL RISK" in regime:
        if "BULLISH ABSORPTION" in judgment and entropy < 1.5:
            return "🔥 SPECULATIVE BUY", "Tail Risk is high but Institutions are absorbing the sell-off. High risk/reward."
        if vpin > 0.80:
            return "🚫 AVOID / EXIT", "Toxic flow and Tail Risk. The 'trapdoor' is open. Do not catch the knife."
        return "⚠️ CAUTION / PROTECT", "Unstable regime. Tighten stops or hedge with puts."

    # 2. TREND PERSISTENCE CHECK (Regime 1 & 2)
    if "1 - BULLISH PERSISTENCE" in regime:
        if "BEARISH EXHAUSTION" in judgment:
            return "📉 REDUCE / TAKE PROFIT", "Trend is real but Big Money is exiting into the retail chase."
        if h_val > 0.62 and cvd_slope > 0:
            return "🚀 STRONG BUY / HOLD", "High-conviction trend with institutional backing. Ride the memory."
        return "✅ HOLD / BUY DIPS", "Healthy persistent uptrend."

    if "2 - BEARISH PERSISTENCE" in regime:
        if "BULLISH ABSORPTION" in judgment:
            return "⏳ WATCH FOR REVERSAL", "Downtrend is persistent but institutions are beginning to buy the floor."
        return "🛑 SELL / SHORT", "Persistent downward memory. No sign of a bottom yet."

    # 3. EQUILIBRIUM CHECK (Regime 3 & 4)
    if "4 - UNSTABLE" in regime:
        return "🔄 SCALP ONLY", "Mean-reversion regime. Buy low, sell high within the range. No long-term trend."

    if "3 - NEUTRAL" in regime:
        if "BULLISH ABSORPTION" in judgment:
            return "➕ ACCUMULATE", "Random walk but smart money is quietly building positions."
        return "💤 NEUTRAL", "Market is a coin flip. Wait for a Hurst breakout (>0.55) or Tail Risk."

    return "🔎 MONITOR", "Metrics are inconclusive. Wait for fractal clarity."


def scan_now(ticker, show_judgment=True):
    print(f"--- Scanning {ticker} Mandelbrot Status ---")

    # Load 1m (Trend) and 1d (Structural Risk)
    data_1m = get_data_persistent(ticker, "1m")
    data_1d = get_data_persistent(ticker, "1d")

    if data_1m.empty or data_1d.empty:
        print("ERROR: Insufficient data returned from Yahoo Finance.")
        return "ERROR - No Data"

    required_1m = max(HURST_WINDOW, VOL_LOOKBACK, 60) + 1
    if len(data_1m) < required_1m:
        print(
            f"ERROR: Not enough intraday data ({len(data_1m)} bars, need {required_1m}).")
        return "ERROR - Insufficient 1m data"

    if len(data_1d) < 2:
        print("ERROR: Not enough daily history.")
        return "ERROR - Insufficient 1d data"

    prices = data_1m['Close'].values
    volumes = data_1m['Volume'].values
    returns_1m = np.diff(np.log(prices))

    # 1. Calculate Core Metrics
    h_val = calculate_hurst_vw(prices, volumes, window=HURST_WINDOW)

    # We calculate the 'Worst Case' Alpha between live intraday and structural daily
    alpha_live = calculate_tail_index_robust(returns_1m, lookback=500)
    alpha_daily = calculate_tail_index_robust(
        data_1d['Close'].pct_change().dropna().values, lookback=500)
    alpha_eff = min(alpha_live, alpha_daily)

    # 2. Intraday Volatility (Standard Deviation of log returns over 30 mins)
    recent_vol = np.std(returns_1m[-VOL_LOOKBACK:])

    # 3. Directional Check (Slope of last hour)
    slope = linregress(np.arange(60), prices[-60:]).slope

    # 4. REGIME CLASSIFICATION
    prev_close = data_1d['Close'].values[-1]
    gap_pct = abs((prices[-1] - prev_close) / prev_close)
    tail_state = "ACTIVE" if recent_vol > VOL_THRESHOLD else "DORMANT"

    if alpha_eff < TAIL_RISKY:
        regime = f"5 - TAIL RISK ({tail_state} Danger of Sudden Move)"
    elif gap_pct > 0.05 and h_val < HURST_TREND_MIN:
        regime = "1 - BULLISH PERSISTENCE (Post-Gap Consolidation)"
    elif h_val > HURST_TREND_MIN:
        if alpha_eff >= TAIL_SAFE:
            regime = "1 - BULLISH PERSISTENCE (Trend is Real)"
        else:
            regime = "2 - BEARISH PERSISTENCE (Trend is Real)"
    elif h_val < HURST_CHOP_MAX:
        regime = "4 - UNSTABLE (Mean Reverting / Chop)"
    else:
        regime = "3 - NEUTRAL / RANDOM WALK"

    # 5. OUTPUT
    print(f"Price:         {prices[-1]:.2f}")
    print(f"Hurst (Trend): {h_val:.3f}")
    print(f"Tail Index:    {alpha_eff:.3f}")
    print(f"Intraday Vol:  {recent_vol:.5f}")
    print(f"RESULT REGIME: {regime}")

    if show_judgment:
        judgment, entropy, vpin, cvd_slope = compute_judgment(
            prices, volumes, data_1m, h_val, alpha_eff)
        print(f"Entropy: {entropy:.2f} (Low is better) | VPIN: {vpin:.2f}")
        print(f"CVD Trend: {'UP' if cvd_slope > 0 else 'DOWN'}")
        print(f"VERDICT: {judgment}")

        # 6. ADD SUGGESTION
        action, reason = generate_suggestion(
            regime, judgment, entropy, alpha_eff, h_val, vpin, cvd_slope)
        print(f"\nSUGGESTION: {action}")
        print(f"REASON:     {reason}")

    print("-" * 45)
    return regime


if __name__ == "__main__":
    # Test on your Core Universe
    import time
    tickers = ["MU", 'GOOG']
    while True:
        for t in tickers:
            scan_now(t)
            # scan_with_judgment(t)
        time.sleep(60)  # Wait 1 minute before next scan
"""
Summary Table for Tail-Index Risk Regimes

Tail Index (α)      Risk Category            Market Behavior
---------------------------------------------------------------
> 3.0               Gaussian / Safe         Movements resemble a normal distribution; standard models are reliable.
2.0 - 3.0           Heavy Tails             Large moves occur more often; risk is elevated but still manageable.
1.55 - 2.0          Unstable Zone           Tail behavior dominates; standard risk metrics begin to fail.
< 1.55              Tail Risk (Regime 5)    High probability of jumps and gaps; use protective sizing.
< 1.0               Structural Collapse     Extreme instability; theoretical mean may not exist.
"""
