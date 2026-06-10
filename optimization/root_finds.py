import numpy as np
from scipy.optimize import brentq, newton

f = lambda x: 0.2 + x * np.cos(3 / x)

x, dx = np.linspace(-1, 1, 1000, retstep=True)

# Find where sign changes between consecutive points.
fvals = f(x)
signs = np.sign(fvals)
sign_changes = np.where(np.diff(signs) != 0)[0]
# Use these indices to get the x-values bracketing the roots.
lower_bounds = x[sign_changes]

# Brent's method
brent_roots = np.array([brentq(f, a, a + dx) for a in lower_bounds])

# Newton's method: requires first derivative of f(x)
fp = lambda x: np.cos(3 / x) + 3 / x * np.sin(3 / x)
newton_roots = np.array([newton(f, a, fp) for a in lower_bounds])
print("Roots of f(x) = 1/5 + x.cos(3/x):")
print(f"{'Brent':11s} {'Newton':11s}")
r = np.vstack((brent_roots, newton_roots)).T
for br, nr in r:
    print(f"{br:11.8f} {nr:11.8f}")