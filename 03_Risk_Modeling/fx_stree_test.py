import pandas as pd
import numpy as np

def run_fx_stress_test():
    # Portfolio Weights
    weights = {
        'CAD_Assets': 0.40, # CLML.TO, XDIV.TO
        'USD_Assets': 0.45, # MSFT, GOOG, CLSE
        'Gold_Unhedged': 0.15 # KILO.TO (Tracks Gold in USD)
    }
    
    # Scenario: 10% Rise in USD/CAD (e.g., from 1.37 to 1.50)
    usd_shock = 0.10
    
    # Calculate Total Portfolio Impact (assuming stock prices are flat)
    # USD Assets gain 1:1 with USD. Gold (unhedged) also gains from the USD rise.
    fx_gain = (weights['USD_Assets'] * usd_shock) + (weights['Gold_Unhedged'] * usd_shock)
    
    print("--- FX Stress Test: 10% USD Appreciation ---")
    print(f"Impact on Portfolio Value: +{fx_gain:.2%}")
    print(f"CAD Value Increase on $4,800: ${4800 * fx_gain:,.2f}")
    
    # Note: CDRs would have shown 0% gain here due to their 0.60% hedging cost drag.
    # This 'FX Buffer' is why direct US stocks are superior for analysts.

run_fx_stress_test()