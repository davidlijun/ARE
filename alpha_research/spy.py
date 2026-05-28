import numpy as np

class SPYRiskEngine:
    def __init__(self, total_capital=1600):
        self.max_trade_risk = total_capital * 0.02 # Max $32 per trade

    def evaluate_spy_trade(self, current_price, strike, premium, iv, dte):
        """
        Hard Gates for Option Entry
        """
        # 1. Delta Check: Ensure we aren't gambling on 'Lotto' strikes
        # (Assuming a BSM calculation here)
        delta = 0.35 # Placeholder
        if delta < 0.20:
            return "REJECT: Strike too far OTM (Gamma risk too high)"

        # 2. IV Check: Don't buy when 'Insurance' is too expensive
        if iv > 25: 
            return "REJECT: IV too high (Vega risk). Sell premium instead."

        # 3. Liquidity Check: Bid-Ask Spread
        # If the spread is > 5% of the premium, you lose too much on entry
        bid_ask_spread = 0.05 # Example
        if bid_ask_spread > (premium * 0.05):
            return "REJECT: Spread too wide (Liquidity risk)."

        return "PASS: Trade within systematic parameters."

# Usage for your $1,600 plan
are = SPYRiskEngine()
status = are.evaluate_spy_trade(750, 755, 2.50, 18, 7)
print(status)

