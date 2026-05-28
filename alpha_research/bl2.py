import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------
# 1. Download market data
# -----------------------------
assets = ["AAPL", "MSFT", "GOOG", "AMZN", "TSLA"]
start = "2020-01-01"

data = yf.download(assets, start=start)["Close"]

# Compute daily returns
returns = data.pct_change().dropna()

# Annualize covariance
Sigma = returns.cov() * 252

# -----------------------------
# 2. Market weights (equal-weight proxy)
# -----------------------------
n = len(assets)
w_mkt = np.ones(n) / n

# -----------------------------
# 3. Risk aversion parameter
# -----------------------------
# Approximate using market return
market_return = returns.mean().mean() * 252
market_variance = np.mean(np.diag(Sigma))

delta = market_return / market_variance

# -----------------------------
# 4. Implied equilibrium returns
# -----------------------------
Pi = delta * Sigma.values @ w_mkt

# -----------------------------
# 5. Investor Views
# -----------------------------
# Example views:
# 1) AAPL will outperform MSFT by 3%
# 2) TSLA will outperform AMZN by 5%

P = np.array([
    [1, -1, 0, 0, 0],
    [0, 0, 0, -1, 1]
])

Q = np.array([0.03, 0.05])

tau = 0.05

# Omega = uncertainty of views
Omega = np.diag(np.diag(P @ (tau * Sigma.values) @ P.T))

# -----------------------------
# 6. Black-Litterman formula
# -----------------------------
tauSigma = tau * Sigma.values

inv_tauSigma = np.linalg.inv(tauSigma)
inv_Omega = np.linalg.inv(Omega)

middle = np.linalg.inv(inv_tauSigma + P.T @ inv_Omega @ P)

mu_bl = middle @ (
    inv_tauSigma @ Pi + P.T @ inv_Omega @ Q
)

# -----------------------------
# 7. Optimal weights
# -----------------------------
weights = np.linalg.inv(Sigma.values) @ mu_bl / delta

# Normalize weights
weights = weights / weights.sum()

# -----------------------------
# 8. Results
# -----------------------------
bl_returns = pd.Series(mu_bl, index=assets)
bl_weights = pd.Series(weights, index=assets)

print("\nBlack-Litterman Expected Returns:")
print(bl_returns)

print("\nOptimal Portfolio Weights:")
print(bl_weights)

# -----------------------------
# 9. Plot weights
# -----------------------------
bl_weights.plot(kind='bar', title='Black-Litterman Portfolio')
plt.show()