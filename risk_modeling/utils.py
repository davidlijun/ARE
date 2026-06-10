# region imports

# endregion
from functools import reduce

import numpy as np
from scipy import stats

# ============================================================================
# FRACTAL ANALYSIS & TAIL RISK FUNCTIONS
# These functions analyze market behavior: whether prices mean-revert (H < 0.5)
# or trend-follow (H > 0.5), and measure tail risk (extreme moves probability)
# ============================================================================


def estimate_hurst(series, min_window=8, max_window=None):
    """Hurst Exponent: measures market mean-reversion (H<0.5) vs trending (H>0.5).
    H=0.5 is random walk. Used to detect market regime and persistence."""
    # Convert to numpy array and get length
    series = np.asarray(series, dtype=np.float64)
    n = len(series)
    # Not enough data - default to random walk (H=0.5)
    if n < 20:
        return 0.5
    # Set max window size if not provided
    if max_window is None:
        max_window = max(n // 4, min_window + 1)
    # Detrend by cumulative mean-centered returns
    y = np.cumsum(series - np.mean(series))
    window_sizes = []
    fluctuations = []
    # Test multiple window sizes to measure scaling behavior
    for window in range(min_window, max_window + 1):
        n_segments = n // window
        if n_segments < 2:
            continue
        f2 = []
        # For each segment, fit a line and measure residual variance
        for i in range(n_segments):
            segment = y[i * window:(i + 1) * window]
            x = np.arange(window)
            # Fit 1st degree polynomial
            trend = np.polyval(np.polyfit(x, segment, 1), x)
            f2.append(np.mean((segment - trend) ** 2))  # Squared deviations
        window_sizes.append(window)
        # Root mean squared fluctuation
        fluctuations.append(np.sqrt(np.mean(f2)))
    # Need enough points for regression
    if len(window_sizes) < 3:
        return 0.5
    # Hurst exponent is the slope in log-log plot of window size vs fluctuation
    slope, _, _, _, _ = stats.linregress(
        np.log(window_sizes), np.log(fluctuations))
    return float(np.clip(slope, 0.0, 1.0))  # Constrain to [0, 1]


def hill_estimator(sorted_abs_returns, k):
    """Hill's tail index estimator: α = 1/E[log(X_i/X_k)].
    Higher α means thinner tails (less extreme events).
    Typical range: 2.0-4.0 for financial returns."""
    # Validate parameters
    if k < 2 or k >= len(sorted_abs_returns):
        return np.nan
    # Get the k largest returns (tail) and the threshold (k+1 return)
    tail = sorted_abs_returns[:k]
    threshold = sorted_abs_returns[k]
    if threshold <= 0:
        return np.nan
    # Compute log ratios of tail elements to threshold
    log_ratios = np.log(tail / threshold)
    log_ratios = log_ratios[log_ratios > 0]  # Keep only positive ratios
    if len(log_ratios) < 2:
        return np.nan
    # Hill estimator formula
    return len(log_ratios) / np.sum(log_ratios)


def dekkers_einmahl_dehaan_estimator(sorted_abs_returns, k):
    """Dekkers-Einmahl-de Haan estimator: improved tail index estimation.
    More robust than Hill for small samples. Uses second moment for bias correction."""
    n = len(sorted_abs_returns)
    # Need sufficient data (at least 5 tail events)
    if k < 5 or k >= n:
        return np.nan
    tail = sorted_abs_returns[:k]
    threshold = sorted_abs_returns[k]
    if threshold <= 0:
        return np.nan
    # Compute log excess over threshold
    log_excess = np.log(tail / threshold)
    log_excess = log_excess[log_excess > 0]
    if len(log_excess) < 5:
        return np.nan
    # Compute first and second moments of log excess
    m1 = np.mean(log_excess)
    m2 = np.mean(log_excess ** 2)
    # Handle edge case
    if m2 <= m1 ** 2:
        return 1 / m1 if m1 > 0 else np.nan
    # Bias-corrected gamma parameter
    gamma = m1 + 1 - 0.5 * (1 / (1 - m1 ** 2 / m2))
    if gamma <= 0:
        return np.nan
    # Return alpha (tail index) clipped to reasonable range
    return float(np.clip(1 / gamma, 0.5, 6.0))


def estimate_tail_index(returns, min_data_for_tail):
    """Estimate tail index (alpha) using robust ensemble of estimators.
    Combines Hill and Dekkers-Einmahl-de Haan across multiple tail sizes."""
    # Clean data: remove NaN and near-zero values
    returns = np.asarray(returns, dtype=np.float64)
    abs_ret = np.abs(returns)
    abs_ret = abs_ret[~np.isnan(abs_ret)]
    abs_ret = abs_ret[abs_ret > 1e-10]
    n = len(abs_ret)
    # Insufficient data
    if n < min_data_for_tail:
        return 2.0  # Default: moderate tail risk
    # Sort in descending order (largest returns first)
    sorted_ret = np.sort(abs_ret)[::-1]
    # Try different tail sizes (k = number of tail observations to use)
    k_min = max(10, int(n * 0.05))   # At least 5% of data
    k_max = min(int(n * 0.25), n // 3)  # At most 25% of data
    k_values = np.linspace(k_min, k_max, 10, dtype=int)
    # Estimate tail index using both methods at each k
    all_estimates = []
    for k in k_values:
        # Hill estimator
        h = hill_estimator(sorted_ret, k)
        if not np.isnan(h) and 0.5 < h < 6:  # Sanity check
            all_estimates.append(('hill', h))
        # Dekkers-Einmahl-de Haan estimator
        d = dekkers_einmahl_dehaan_estimator(sorted_ret, k)
        if not np.isnan(d) and 0.5 < d < 6:
            all_estimates.append(('deh', d))
    # Need enough valid estimates
    if len(all_estimates) < 3:
        return 2.0
    # Adaptive weighting: if Hill is stable (low std dev), trust it more
    hill_only = [e[1] for e in all_estimates if e[0] == 'hill']
    hill_std = np.std(hill_only) if len(hill_only) > 2 else np.inf
    weights = {'hill': 0.6, 'deh': 0.4} if hill_std < 0.3 else {
        'hill': 0.5, 'deh': 0.5}
    # Compute weighted average
    weighted_sum = sum(weights[m] * a for m, a in all_estimates)
    weight_total = sum(weights[m] for m, _ in all_estimates)
    return float(np.clip(weighted_sum / weight_total, 0.5, 5.0)) if weight_total > 0 else 2.0


def compute_mf_width(returns_arr):
    """Multifractal width: range of Hurst exponents across moments.
    Higher width indicates regime changes (market transitions from mean-revert to trending)."""
    # Clean data
    returns_arr = np.asarray(returns_arr, dtype=np.float64)
    returns_arr = returns_arr[~np.isnan(returns_arr)]
    n = len(returns_arr)
    if n < 50:  # Need enough history
        return 0.0
    # Detrended profile
    profile = np.cumsum(returns_arr - np.mean(returns_arr))
    max_scale = n // 4
    scales = np.unique(np.logspace(
        np.log10(4), np.log10(max_scale), 12).astype(int))

    def get_hurst_at_q(q):
        """Compute Hurst exponent for specific moment q."""
        log_scales, log_Fq = [], []
        for scale in scales:
            n_seg = n // scale
            if n_seg < 2:

                continue
            # Measure variance within each segment at this scale
            variances = []
            for i in range(n_seg):

                seg = profile[i * scale:(i + 1) * scale]

                x = np.arange(len(seg))

                var = np.mean(

                    (seg - np.polyval(np.polyfit(x, seg, 1), x)) ** 2)

                if var > 0:

                    variances.append(var)
            if len(variances) < 2:

                continue
            variances = np.array(variances)
            if q < 0:

                variances = np.clip(variances, 1e-20, None)  # Avoid log(0)
            # q-th moment fluctuation exponent
            Fq = np.mean(variances ** (q / 2)) ** (1 / q)
            if Fq > 0 and np.isfinite(Fq):

                log_scales.append(np.log(scale))

                log_Fq.append(np.log(Fq))
            # Hurst at this moment is the slope in log-log plot
            if len(log_scales) >= 3:
                slope, _, r_value, _, _ = stats.linregress(log_scales, log_Fq)
                if r_value ** 2 > 0.5:  # Only accept good fits

                    return slope
            return np.nan

    # Compute Hurst for small and large moments
    h_low = get_hurst_at_q(0.5)   # Sensitive to small moves
    h_high = get_hurst_at_q(3)    # Sensitive to large moves
    # Multifractal width is the difference
    if np.isfinite(h_low) and np.isfinite(h_high):
        return abs(h_low - h_high)
    return 0.0


# ============================================================================
# TECHNICAL INDICATORS
# Standard charting indicators used to identify entry/exit signals
# ============================================================================

def compute_sma(prices, period):
    """Simple Moving Average: average of last 'period' prices.
    Used for trend identification (price above SMA50 = uptrend)."""
    if len(prices) < period:
        return prices[-1] if len(prices) > 0 else 0.0
    return float(np.mean(prices[-period:]))


def compute_ema(prices, period):
    """Exponential Moving Average: weights recent prices more heavily.
    More responsive to price changes than SMA."""
    prices = np.asarray(prices, dtype=np.float64)
    if len(prices) < period:
        return prices[-1] if len(prices) > 0 else 0.0
    # EMA multiplier (smoothing factor)
    multiplier = 2.0 / (period + 1)
    # Initialize with simple average of first 'period' prices
    ema = np.mean(prices[:period])
    # Update EMA for each subsequent price
    for p in prices[period:]:
        ema = (p - ema) * multiplier + ema
    return float(ema)


def compute_macd(prices, fast=12, slow=26, signal=9):
    """MACD (Moving Average Convergence Divergence):
    - MACD line: fast EMA - slow EMA (momentum)
    - Signal line: EMA of MACD (trend)
    - Histogram: MACD - Signal (crossover signal)
    Positive histogram with price above MA = bullish."""
    prices = np.asarray(prices, dtype=np.float64)
    if len(prices) < slow + signal:
        return 0.0, 0.0, 0.0
    # Get current EMAs
    ema_fast = compute_ema(prices, fast)
    ema_slow = compute_ema(prices, slow)
    # MACD line is the difference
    macd_line = ema_fast - ema_slow
    # Build MACD series to smooth into signal
    macd_series = []
    mult_f = 2.0 / (fast + 1)
    mult_s = 2.0 / (slow + 1)
    ef = np.mean(prices[:fast])
    es = np.mean(prices[:slow])
    # Compute MACD at each point
    for p in prices[max(fast, slow):]:
        ef = (p - ef) * mult_f + ef
        es = (p - es) * mult_s + es
        macd_series.append(ef - es)
    # Not enough MACD values to signal
    if len(macd_series) < signal:
        return macd_line, 0.0, macd_line
    # Smooth MACD with signal EMA
    mult_sig = 2.0 / (signal + 1)
    sig_ema = np.mean(macd_series[:signal])
    for m in macd_series[signal:]:
        sig_ema = (m - sig_ema) * mult_sig + sig_ema
    # Histogram is the difference between MACD and its signal
    histogram = macd_series[-1] - sig_ema
    return macd_series[-1], sig_ema, histogram


def compute_rsi(prices, period=14):
    """Relative Strength Index (RSI): momentum oscillator (0-100).
    RSI < 30 = oversold (potential buy). RSI > 70 = overbought (potential sell)."""
    prices = np.asarray(prices)
    if len(prices) < period + 1:
        return 50.0  # Neutral
    # Compute price changes (deltas)
    delta = np.diff(prices)
    # Separate gains and losses
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    # Average over the period
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    # Avoid division by zero
    if avg_loss < 1e-10:
        return 100.0  # All gains = max RSI
    # RSI formula: 100 - (100 / (1 + RS)) where RS = avg_gain / avg_loss
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_bollinger_pctb(prices, period=20, std_dev=2):
    """Bollinger Bands %B: position within upper/lower bands (0-1).
    0 = at lower band (oversold). 1 = at upper band (overbought)."""
    prices = np.asarray(prices)
    if len(prices) < period:
        return 0.5  # Middle
    # Get recent window
    window = prices[-period:]
    # Compute mean and standard deviation
    ma = np.mean(window)
    std = np.std(window, ddof=1)
    # Bands
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    # Avoid division by zero
    if upper - lower < 1e-10:
        return 0.5
    # %B = (price - lower) / (upper - lower)
    return (prices[-1] - lower) / (upper - lower)


def compute_atr_normalized(highs, lows, closes, period=14):
    """Average True Range (normalized): volatility measure as % of price.
    True Range = max(high-low, |high-prev_close|, |low-prev_close|).
    Higher ATR% = higher volatility."""
    highs, lows, closes = np.asarray(
        highs), np.asarray(lows), np.asarray(closes)
    if len(closes) < period + 1:
        return 0.015  # Default 1.5% volatility
    # Compute true ranges over recent period
    trs = []
    for i in range(-period, 0):
        # TR is max of 3 distances
        trs.append(max(
            highs[i] - lows[i],                # High-low range
            # Distance from previous close to high
            abs(highs[i] - closes[i - 1]),
            # Distance from previous close to low
            abs(lows[i] - closes[i - 1])
        ))
    # Normalize by current price
    return np.mean(trs) / closes[-1] if closes[-1] > 0 else 0.015


def compute_volume_ratio(volumes, period=20):
    """Current volume relative to average volume.
    > 1.0 = above average (strong signal). < 1.0 = weak volume."""
    volumes = np.asarray(volumes)
    if len(volumes) < period:
        return 1.0
    # Average volume over period
    avg = np.mean(volumes[-period:])
    # Ratio of current to average
    return volumes[-1] / avg if avg > 0 else 1.0


def compute_vwap_deviation(closes, highs, lows, volumes, period=20):
    """Volume Weighted Average Price deviation.
    VWAP is the fair value; positive dev = price above fair value (overvalued).
    As % of price."""
    closes, highs, lows, volumes = [np.asarray(
        a) for a in [closes, highs, lows, volumes]]
    if len(closes) < period:
        return 0.0
    # Typical price = (high + low + close) / 3
    tp = (highs[-period:] + lows[-period:] + closes[-period:]) / 3.0
    # Get volumes for the period
    vol = volumes[-period:]
    # Sum of volumes
    total_vol = np.sum(vol)
    if total_vol <= 0:
        return 0.0
    # VWAP = sum(tp * vol) / sum(vol)
    vwap = np.sum(tp * vol) / total_vol
    # Deviation as % of current price
    return (closes[-1] - vwap) / closes[-1] if closes[-1] > 0 else 0.0

# ============================================================================
# VOLATILITY METRICS
# Measures market uncertainty and option pricing implications
# ============================================================================


def compute_realized_vol(returns_arr, window=20):
    """Realized volatility: annualized std dev of recent returns.
    Uses historical returns over 'window' days, annualized to ~252 trading days."""
    if len(returns_arr) < window:
        window = len(returns_arr)
    if window < 5:
        return 0.15  # Default 15% vol if insufficient data
    # Annual volatility = daily std * sqrt(252)
    return float(np.std(returns_arr[-window:]) * np.sqrt(252))


def compute_vol_of_vol(returns_arr, sub_window=5, n_subs=4):
    """Volatility of volatility: std dev of rolling volatility windows.
    Measures if market is becoming more/less uncertain.
    High vol-of-vol suggests regime instability."""
    # Need enough data for multiple sub-windows
    if len(returns_arr) < sub_window * n_subs:
        return 0.0
    # Compute volatility for each recent sub-window
    sub_vols = []
    for i in range(n_subs):
        end = len(returns_arr) - i * sub_window
        start = end - sub_window
        if start < 0:
            break
        # Standard deviation of each window
        sub_vols.append(np.std(returns_arr[start:end]))
    # Return std dev of those volatilities
    return float(np.std(sub_vols)) if len(sub_vols) > 1 else 0.0


def compute_iv_rv_ratio(ticker, realized_vol, option_iv_cache):
    """IV/RV Ratio: option implied vol vs historical realized vol.
    > 1.0 = options expensive (consider selling). < 1.0 = options cheap (consider buying)."""
    # Avoid division by zero
    if realized_vol < 0.01:
        return 1.0
    # Get most recent implied vol for this ticker from cache
    recent_keys = [(d, t) for (d, t) in option_iv_cache.keys() if t == ticker]
    if not recent_keys:
        return 1.0  # No IV data, neutral
    # Sort by date (descending) and get most recent
    recent_keys.sort(reverse=True)
    iv = option_iv_cache.get(recent_keys[0])
    if iv is None:
        return 1.0
    # Return the ratio
    return iv / realized_vol

# ============================================================================
# FEATURE ENGINEERING & REGIME CLASSIFICATION
# Extract all technical, volatility, and fractal features for a given ticker
# ============================================================================


def compute_features(ticker, price_data, min_data_for_trading, min_data_for_tail, option_iv_cache):
    """Compute all features needed for regime classification and signal generation.
    Returns dict with 20+ features or None if insufficient data."""
    # Extract price series
    pd = price_data[ticker]
    closes = pd['close']
    n = len(closes)
    # Not enough historical data
    if n < min_data_for_trading:
        return None

    # Convert to numpy arrays for computation
    closes_arr = np.array(closes)
    highs_arr = np.array(pd['high'])
    lows_arr = np.array(pd['low'])
    volumes_arr = np.array(pd['volume'])

    # Core returns series (log returns for volatility calculations)
    log_returns = np.diff(np.log(closes_arr))
    if len(log_returns) < min_data_for_trading - 1:
        return None

    # -------- FRACTAL & TAIL ANALYSIS --------
    # Hurst exponent at 3 timescales: short (20d), medium (60d), long (120d)
    hurst_short = estimate_hurst(log_returns[-min(20, len(log_returns)):])
    hurst_med = estimate_hurst(
        log_returns[-min(60, len(log_returns)):])    # Intermediate
    hurst_long = estimate_hurst(
        log_returns[-min(120, len(log_returns)):])  # Long-term
    hurst = hurst_med  # Use medium-term as primary Hurst

    # Tail index: how likely are extreme moves?
    tail_index = estimate_tail_index(log_returns, min_data_for_tail)
    # Multifractal width: regime change signal
    mf_width = compute_mf_width(log_returns[-min(120, len(log_returns)):])

    # -------- VOLATILITY METRICS --------
    realized_vol = compute_realized_vol(log_returns, window=20)
    vol_of_vol = compute_vol_of_vol(log_returns)
    iv_rv_ratio = compute_iv_rv_ratio(ticker, realized_vol, option_iv_cache)

    # -------- TECHNICAL INDICATORS --------
    rsi = compute_rsi(closes_arr, period=14)              # Momentum (0-100)
    bb_pctb = compute_bollinger_pctb(
        closes_arr, period=20)  # Position in bands (0-1)
    atr = compute_atr_normalized(
        highs_arr, lows_arr, closes_arr, period=14)  # Volatility %
    volume_ratio = compute_volume_ratio(volumes_arr, period=20)  # Vol strength
    vwap_dev = compute_vwap_deviation(
        closes_arr, highs_arr, lows_arr, volumes_arr, period=20)  # Fair value

    # -------- MOVING AVERAGES & TRENDS --------
    sma_50 = compute_sma(closes_arr, 50)   # Long-term trend
    sma_20 = compute_sma(closes_arr, 20)   # Short-term trend
    macd_line, macd_signal, macd_hist = compute_macd(closes_arr)
    price = closes_arr[-1]
    # Is price above key moving average? (1=yes, 0=no)
    above_sma50 = 1.0 if price > sma_50 else 0.0
    # Is short MA above long MA? (uptrend signal)
    sma_trend = (sma_20 - sma_50) / sma_50 if sma_50 > 0 else 0.0

    # -------- RECENT RETURNS --------
    ret_1d = log_returns[-1]  # Latest day return
    # 5-day cumulative
    ret_5d = np.sum(log_returns[-min(5, len(log_returns)):])
    # 20-day cumulative
    ret_20d = np.sum(log_returns[-min(20, len(log_returns)):])

    # -------- RISK METRICS --------
    # 20-day drawdown: how far below peak?
    drawdown_20d = 0.0
    if n >= 20:
        peak = np.max(closes_arr[-20:])
        drawdown_20d = (price - peak) / peak if peak > 0 else 0.0

    # -------- DIVERGENCE METRICS --------
    # Is short-term persistence diverging from long-term?
    hurst_divergence = hurst_short - hurst_long

    # Return all computed features
    return {
        # Fractal metrics
        'hurst': hurst, 'hurst_short': hurst_short, 'hurst_med': hurst_med,
        'hurst_long': hurst_long, 'hurst_divergence': hurst_divergence,
        # Tail risk
        'tail_index': tail_index, 'mf_width': mf_width,
        'realized_vol': realized_vol, 'vol_of_vol': vol_of_vol,
        'iv_rv_ratio': iv_rv_ratio,
        # Technical indicators
        'rsi': rsi, 'bb_pctb': bb_pctb, 'atr': atr,
        'volume_ratio': volume_ratio, 'vwap_dev': vwap_dev,
        # Trends
        'above_sma50': above_sma50, 'sma_trend': sma_trend,
        'macd_line': macd_line, 'macd_signal': macd_signal, 'macd_hist': macd_hist,
        # Returns
        'ret_1d': ret_1d, 'ret_5d': ret_5d, 'ret_20d': ret_20d,
        # Risk
        'drawdown_20d': drawdown_20d, 'price': price,
    }


def classify_regime(features):
    """Classify market regime (0-4) based on fractal and risk analysis.

    Regimes:
    - 0: Trending Up (persistent, bullish conditions)
    - 1: Trending Down (persistent, bearish conditions)
    - 2: Mean-Reverting (anti-persistent, choppy, good for ranging)
    - 3: Elevated Risk (elevated vol/tail, uncertain conditions)
    - 4: Crisis (extreme vol/tail/drawdown, avoid trading)

    Returns: (regime, danger_score) where danger_score in [0, 1]
    """
    # Extract key features
    h_short = features['hurst_short']
    h_med = features['hurst_med']
    h_long = features['hurst_long']
    rv = features['realized_vol']
    tail = features['tail_index']
    mf = features['mf_width']
    drawdown = features['drawdown_20d']
    ret_20d = features['ret_20d']
    above_sma50 = features['above_sma50']
    sma_trend = features['sma_trend']
    macd_hist = features['macd_hist']

    # -------- DANGER SCORE --------
    # Composite risk indicator: high vol, thin tails, multifractal width, large drawdowns
    # 0 = calm, 1 = very volatile
    vol_score = np.clip((rv - 0.10) / 0.35, 0, 1)
    # 0 = thick tails (safer), 1 = thin tails (crisis)
    tail_score = np.clip((2.5 - tail) / 1.5, 0, 1)
    # 0 = stable, 1 = regime instability
    mf_score = np.clip(mf / 0.5, 0, 1)
    # 0 = at peak, 1 = 10%+ below peak
    dd_score = np.clip(-drawdown / 0.10, 0, 1)
    # Weighted average of risk factors
    danger = 0.35 * vol_score + 0.15 * tail_score + 0.20 * mf_score + 0.25 * dd_score

    # -------- CRISIS DETECTION --------
    # Thin tails (< 1.8) with high regime instability = likely crash
    if tail < 1.8 and mf > 0.4:
        danger = max(danger, 0.7)
    # Thin tails with extreme volatility = systemic risk
    if tail < 1.8 and rv > 0.4:
        danger = max(danger, 0.5)

    # If danger too high, override all other analysis
    if danger >= 0.7:
        return 4, danger  # CRISIS regime
    if danger >= 0.5:
        return 3, danger  # ELEVATED RISK regime

    # -------- FRACTAL-BASED CLASSIFICATION --------
    # Persistent market: prices tend to follow recent trend (momentum)
    fractal_persistent = h_med > 0.52 and h_short > 0.48
    # Anti-persistent: mean-reverting (prices bounce back toward average)
    fractal_anti = h_med < 0.48 or h_short < 0.45

    # REGIME 2: Mean-reverting (choppy, range-bound)
    if fractal_anti:
        return 2, danger

    # REGIME 0/1: Trending (persistent) - determine direction by trend signals
    if fractal_persistent:
        # Strong uptrend: positive returns + price above SMA50
        if ret_20d > 0 and above_sma50 > 0.5:
            return 0, danger
        # Strong downtrend: negative returns + price below SMA50
        if ret_20d < 0 and above_sma50 < 0.5:
            return 1, danger
        # Uptrend by moving average alignment
        if above_sma50 > 0.5 and sma_trend > 0:
            return 0, danger
        # Downtrend by moving average alignment
        if above_sma50 < 0.5 and sma_trend < 0:
            return 1, danger
        # Default to direction of recent returns
        if ret_20d > 0.0:
            return 0, danger
        else:
            return 1, danger

    # FALLBACK: Use technical indicators if fractal signals are ambiguous
    # All momentum and trend indicators aligned bullish
    if above_sma50 > 0.5 and sma_trend > 0 and macd_hist > 0 and h_med > 0.48:
        return 0, danger
    # All momentum and trend indicators aligned bearish
    if above_sma50 < 0.5 and sma_trend < 0 and macd_hist < 0 and h_med > 0.48:
        return 1, danger

    return 3, danger


def generate_signal(features, regime, danger, cfg):
    """Generate trading signal (buy/sell/hold) with strength based on regime and technicals.

    Returns dict with:
    - direction: 1 (BUY), -1 (SELL), 0 (HOLD)
    - strength: [0, 1] signal confidence
    - reason: string describing signal reason
    - Plus all input features for logging/analysis
    """
    # Extract technical features
    rsi = features['rsi']
    bb_pctb = features['bb_pctb']
    ret_5d = features['ret_5d']
    ret_1d = features['ret_1d']
    ret_20d = features['ret_20d']
    volume_ratio = features['volume_ratio']
    iv_rv_ratio = features.get('iv_rv_ratio', 1.0)
    macd_hist = features['macd_hist']
    above_sma50 = features['above_sma50']
    h_med = features['hurst_med']
    h_short = features['hurst_short']
    tail = features['tail_index']
    mf = features['mf_width']

    # Include all features in base output
    base = {'regime': regime, 'danger_score': danger, **features}

    # -------- CRISIS MODE: NO TRADING --------
    if regime >= 4:
        return {'direction': 0, 'strength': 0.0, 'reason': 'crisis_regime', **base}

    regime_penalty = 1.0

    # -------- HELPER FUNCTIONS --------
    def fractal_confidence(h, threshold, side='above'):
        """Confidence score based on distance from Hurst threshold.
        Higher H above threshold = higher confidence for trending signal."""

        if side == 'above':
            return float(np.clip((h - threshold) / 0.15, 0.3, 1.0))
        return float(np.clip((threshold - h) / 0.15, 0.3, 1.0))

    def tail_mispricing(tail_idx, direction):
        """Adjust signal strength based on tail risk perception.
        Thin tails = overpriced options = higher strength for buying.

        Thick tails = underpriced options = lower strength for buying.
        """
        if direction > 0:
            # Buy signal: boost if options are cheap (thick tails)
            return float(np.clip(2.5 / max(tail_idx, 0.8), 0.6, 1.25))
        # Sell signal: boost less aggressively on cheap puts
        return float(np.clip(2.5 / max(tail_idx, 0.8), 0.6, 1.15))

    def iv_rv_adj(ratio, direction):
        """Adjust signal for IV/Realized Vol ratio.
        IV > RV = options expensive = reduce position.
        IV < RV = options cheap = increase position.
        """
        if direction > 0:
            # BUY adjustment
            if ratio < 0.90:  # Calls very cheap
                return 1.12
            if ratio < 1.0:   # Calls somewhat cheap

                return 1.05
            if ratio > 1.25:  # Calls expensive

                return 0.85
            return 1.0
        else:
            # SELL adjustment
            if ratio < 0.90:  # Puts very cheap

                return 1.10
            if ratio > 1.25:  # Puts expensive

                return 0.88
            return 1.0

    # -------- REGIME 0: UPTREND --------
    if regime == 0:
        # Confidence metrics for uptrend signal
        # How strong is persistence?
        fc = fractal_confidence(h_med, 0.55, 'above')
        # Option pricing adjustment (bullish)
        tm = tail_mispricing(tail, 1)
        iv_adj = iv_rv_adj(iv_rv_ratio, 1)              # IV premium adjustment

        # SIGNAL 1: Pullback buy in uptrend (RSI oversold, recent weakness)
        if (rsi < cfg['rsi_oversold'] and ret_5d < -0.02 and bb_pctb < 0.5 and macd_hist > -0.5 and above_sma50 > 0.5):
            # Technical quality score: reward lower RSI (stronger oversold)
            tech_q = float(
                np.clip((cfg['rsi_oversold'] - rsi) / 25.0 + 0.45, 0.4, 0.95))
            # Composite strength: fractal * tail_adjustment * technical_quality * option_adjustment
            strength = fc * tm * tech_q * iv_adj * regime_penalty
            return {'direction': 1, 'strength': np.clip(strength, 0, 1.0), 'reason': 'trend_pullback_buy', **base}

        # SIGNAL 2: Continuation buy in uptrend (momentum building)
        if (ret_5d > 0.02 and rsi > 52 and rsi < 70 and macd_hist > 0 and bb_pctb > 0.5 and bb_pctb < 0.9 and above_sma50 > 0.5):
            # Technical quality: reward strong recent moves
            tech_q = float(np.clip(ret_5d * 20 + 0.40, 0.4, 0.90))
            strength = fc * tm * tech_q * iv_adj * regime_penalty
            return {'direction': 1, 'strength': np.clip(strength, 0, 1.0), 'reason': 'trend_continuation', **base}

    # -------- REGIME 1: DOWNTREND --------
    if regime == 1:
        fc = fractal_confidence(h_med, 0.55, 'above')  # Persistence confidence
        # Option pricing adjustment (bearish)
        tm = tail_mispricing(tail, -1)
        iv_adj = iv_rv_adj(iv_rv_ratio, -1)             # IV premium adjustment

        # SIGNAL 1: Pullback sell in downtrend (RSI overbought, bounce attempt)
        if (rsi > cfg['rsi_overbought'] and ret_5d > 0.02 and bb_pctb > 0.5 and macd_hist < 0.5 and above_sma50 < 0.5):
            # Technical quality: reward higher RSI (stronger overbought)
            tech_q = float(
                np.clip((cfg['rsi_overbought'] - rsi) / 25.0 + 0.45, 0.4, 0.95))
            strength = fc * tm * tech_q * iv_adj * regime_penalty
            return {'direction': -1, 'strength': np.clip(strength, 0, 1.0), 'reason': 'trend_pullback_sell', **base}

        # SIGNAL 2: Continuation sell in downtrend (momentum declining)
        if (ret_5d < -0.02 and rsi < 48 and rsi > 30 and macd_hist < 0

            and bb_pctb < 0.5 and bb_pctb > 0.1 and above_sma50 < 0.5

                and tail < 2.8 and mf > 0.18):
            # Technical quality: reward strong downside moves
            tech_q = float(np.clip(abs(ret_5d) * 20 + 0.40, 0.4, 0.90))
            strength = fc * tm * tech_q * iv_adj * regime_penalty
            return {'direction': -1, 'strength': np.clip(strength, 0, 1.0), 'reason': 'downtrend_continuation', **base}

    # -------- REGIME 2: MEAN-REVERTING --------
    if regime == 2:
        # Anti-persistent regime: prefer reversions, not continuations
        fc = fractal_confidence(h_med, 0.42, 'below')  # How anti-persistent?
        tm = 1.0                                        # No directional bias on tail risk
        iv_adj_buy = iv_rv_adj(iv_rv_ratio, 1)
        iv_adj_sell = iv_rv_adj(iv_rv_ratio, -1)

        # SIGNAL 1: Mean reversion buy (extreme oversold)
        if (rsi < cfg['rsi_mr_oversold'] and bb_pctb < 0.25 and ret_20d > -0.08 and ret_1d > -0.04):

            # Technical quality: severity of oversold
            tech_q = float(
                np.clip((cfg['rsi_mr_oversold'] - rsi) / 18.0 + 0.45, 0.4, 0.90))
            # Boost signal if implied vol is cheap (good entry for calls)
            if iv_rv_ratio < 1.0:
                tech_q = min(tech_q + 0.08, 0.95)
            strength = fc * tm * tech_q * iv_adj_buy * regime_penalty
            return {'direction': 1, 'strength': np.clip(strength, 0, 1.0), 'reason': 'mean_reversion_buy', **base}

        # SIGNAL 2: Mean reversion sell (extreme overbought)
        if (rsi > cfg['rsi_mr_overbought'] and bb_pctb > 0.95 and ret_20d < 0.08 and ret_1d < 0.02 and above_sma50 < 0.5):
            # Technical quality: severity of overbought
            tech_q = float(
                np.clip((rsi - cfg['rsi_mr_overbought']) / 18.0 + 0.45, 0.4, 0.90))
            # Boost if implied vol is cheap (good entry for puts)
            if iv_rv_ratio < 1.0:
                tech_q = min(tech_q + 0.08, 0.95)
            strength = fc * tm * tech_q * iv_adj_sell * regime_penalty
            return {'direction': -1, 'strength': np.clip(strength, 0, 1.0), 'reason': 'mean_reversion_sell', **base}

    # -------- NO SIGNAL --------
    return {'direction': 0, 'strength': 0.0, 'reason': 'no_signal', **base}


def compute_position_size(signal, position_size_max):
    """Compute position size by scaling signal strength and adjusting for risk metrics.
    
    Risk adjustments:
    - Tail index: thinner tails reduce position (more crash risk)
    - ATR: high volatility reduces position (wider stops needed)
    - Danger score: elevated risk reduces position
    
    Returns position size as % of account (typically 1-5%).
    """
    # Base size from signal strength
    base_size = position_size_max * signal['strength']
    # Extract risk metrics
    tail_index = signal.get('tail_index', 2.0)
    atr = signal.get('atr', 0.015)
    danger = signal.get('danger_score', 0.0)
    # -------- RISK ADJUSTMENTS --------
    # Tail adjustment: thin tails (low alpha) = lower positions
    tail_adj = min(tail_index / 2.5, 1.0)
    # ATR adjustment: high volatility = lower positions (1.5% ATR is target)
    atr_adj = 0.02 / atr if atr > 0.02 else 1.0
    # Danger adjustment: reduce by danger score (0.5 danger = 50% size reduction)
    danger_adj = max(1.0 - danger, 0.4)
    # Take minimum risk adjustment (most conservative)
    risk_adj = min(tail_adj, atr_adj, danger_adj)
    # Apply risk adjustment but floor at 30% of original signal size
    base_size *= max(risk_adj, 0.3)
    # Clip to reasonable range (minimum 3%, maximum based on config)
    return np.clip(base_size, 0.03, position_size_max)
