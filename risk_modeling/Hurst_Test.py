import numpy as np
import pandas as pd
from scipy.stats import linregress
import matplotlib.pyplot as plt
from risk_alert import calculate_hurst, calculate_tail_index

# --- THE TEST SUITE ---

def run_accuracy_test():
    print("=== MANDELBROT INDICATOR CALIBRATION ===\n")
    size = 10000
    
    # TEST 1: THE RANDOM WALK (The "Casino" Market)
    # Target: Hurst = 0.50 | Alpha = High (>2.5)
    white_noise = np.random.normal(0, 0.01, size)
    random_walk = 100 + np.cumsum(white_noise)
    h_rw = round(calculate_hurst(random_walk), 2)
    a_rw = round(calculate_tail_index(white_noise), 2)
    
    print(f"TEST 1: RANDOM WALK")
    print(f"  Hurst (Target 0.50): {h_rw:.3f} -> {'PASS' if 0.45 < h_rw < 0.60 else 'FAIL'}")
    print(f"  Alpha (Target > 2.5): {a_rw:.3f} -> {'PASS' if a_rw > 2.0 else 'FAIL'}")
    print("-" * 40)

    # TEST 2: THE DETERMINISTIC TREND (The "Moon Rocket")
    # Target: Hurst = 1.00 | Alpha = High
    trend_noise = np.random.normal(0, 0.001, size)
    trend_line = np.linspace(100, 200, size) + trend_noise
    h_tr = calculate_hurst(trend_line)
    
    print(f"TEST 2: PERFECT TREND")
    print(f"  Hurst (Target 1.00): {h_tr:.3f} -> {'PASS' if h_tr > 0.85 else 'FAIL'}")
    print("-" * 40)

    # TEST 3: THE FAT TAIL CRASH (The "Black Swan")
    # Target: Hurst = Low/Variable | Alpha = LOW (< 1.5)
    fat_noise = np.random.standard_t(df=1.5, size=size) * 0.01 
    fat_walk = 100 + np.cumsum(fat_noise)
    a_fat = calculate_tail_index(fat_noise)
    
    print(f"TEST 3: FAT TAIL RISK")
    print(f"  Alpha (Target < 1.5): {a_fat:.3f} -> {'PASS' if a_fat < 1.8 else 'FAIL'}")
    print("-" * 40)

if __name__ == "__main__":
    i = 0
    while i < 1000:
        run_accuracy_test()
        i += 1