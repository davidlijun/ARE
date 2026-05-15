from engine import AnalyticalResearchEngine
from data_loader import AREDataLoader

# Initialize
are = AnalyticalResearchEngine()
loader = AREDataLoader()

# 1. Update HMM Regime
macro_data = loader.fetch_macro_data()
regime = are.get_market_regime(macro_data)
print(f"Current Market State: {regime}")

# 2. Check Options Stability (GEX)
options, spot = loader.fetch_gex_data("SPY")
total_gex, gex_status = are.get_gamma_exposure(options, spot)
print(f"SPY GEX: {total_gex:.2f} | Status: {gex_status}")

# 3. Check for Toxicity (VPIN) in MU
mu_intraday = loader.fetch_intraday_data("MU")
toxicity = are.get_vpin(mu_intraday)
print(f"MU Liquidity Toxicity (VPIN): {toxicity:.4f}")

# 4. Set Risk Stops
stop_level = are.get_atr_stop(mu_intraday.rename(columns={'Close': 'close', 'High': 'high', 'Low': 'low'}))
print(f"MU Dynamic ATR Stop Level: {stop_level:.2f}")