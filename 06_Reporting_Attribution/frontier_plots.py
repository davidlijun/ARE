import plotly.graph_objects as go
from pypfopt import CLA, plotting, EfficientFrontier
import numpy as np

def plot_institutional_frontier(mu, S, optimized_weights, rf_rate=0.04):
    """
    Generates a CFA-level interactive Efficient Frontier plot.
    """
    # 1. Generate the Frontier Curve
    # CLA (Critical Line Algorithm) is better for generating the entire curve
    cla = CLA(mu, S)
    (ret, vol, weights) = cla.efficient_frontier()

    # 2. Calculate Individual Asset Performance
    asset_vols = np.sqrt(np.diag(S))
    asset_rets = mu

    # 3. Calculate Your Optimized Portfolio Performance
    # We use your weights from the Quadratic Utility optimization
    portfolio_ret = np.dot(list(optimized_weights.values()), mu)
    portfolio_vol = np.sqrt(np.dot(list(optimized_weights.values()), np.dot(S, list(optimized_weights.values()))))

    # --- PLOTLY CONSTRUCTION ---
    fig = go.Figure()

    # A. Add the Frontier Line
    fig.add_trace(go.Scatter(
        x=vol, y=ret, mode='lines',
        name='Efficient Frontier',
        line=dict(color='white', width=2)
    ))

    # B. Add Individual Assets
    fig.add_trace(go.Scatter(
        x=asset_vols, y=asset_rets,
        mode='markers+text',
        name='Individual Assets',
        text=list(mu.index),
        textposition="top center",
        marker=dict(size=10, color='#1f77b4', symbol='circle')
    ))

    # C. Add Your Optimized Portfolio (The Star)
    fig.add_trace(go.Scatter(
        x=[portfolio_vol], y=[portfolio_ret],
        mode='markers',
        name='ARE Optimized Portfolio',
        marker=dict(size=18, color='#ff7f0e', symbol='star', line=dict(width=2, color='white'))
    ))

    # Formatting for Institutional Reporting
    fig.update_layout(
        title="ARE Efficient Frontier & Asset Universe",
        xaxis_title="Annualized Volatility (Risk)",
        yaxis_title="Annualized Expected Return",
        template="plotly_dark",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        hovermode="closest"
    )

    return fig

