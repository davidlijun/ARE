import numpy as np
from scipy.stats import linregress

from risk_alert import calculate_tail_index, calculate_hurst
# TEST 1: RANDOM WALK (Should be ~0.50)
random_data = np.cumsum(np.random.randn(500))
print(f"Random Walk Test: {calculate_hurst(random_data):.3f}")

# TEST 2: STRONG TREND (Should be > 0.70)
# TEST 3: FAT TAIL (Crash Risk)
crash_data = np.random.randn(500)
crash_data[250] = -10.0 # Simulate a "Black Swan" crash
print(f"Tail Index (Low Alpha = Danger): {calculate_tail_index(crash_data):.3f}")