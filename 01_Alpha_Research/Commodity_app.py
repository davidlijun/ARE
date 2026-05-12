import streamlit as st
import plotly.graph_objects as go

from Commodity import load_gold, compute_fibonacci, trend_slope

st.set_page_config(layout="wide", page_title="Gold Fibonacci Quant View")

st.title("Gold (GC=F) – Fibonacci Support & Trend")

# -------------------------
# Sidebar controls
# -------------------------
lookback = st.sidebar.slider("Fibonacci lookback (days)", 120, 800, 252)
trend_window = st.sidebar.slider("Trend window (days)", 20, 120, 60)

# -------------------------
# Load data
# -------------------------
@st.cache_data
def get_data():
    return load_gold()

df = get_data()

# -------------------------
# Compute quant metrics
# -------------------------
low, high, fibs = compute_fibonacci(df, lookback)
slope = trend_slope(df, trend_window)

# -------------------------
# Plot
# -------------------------
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["Date"],
    y=df["Close"],
    name="Gold Price",
    line=dict(color="gold", width=2)
))

# Fibonacci levels
for label, level in fibs.items():
    fig.add_hline(
        y=level,
        line_dash="dash",
        opacity=0.6,
        annotation_text=f"Fib {label}: {level:,.0f}",
        annotation_position="right"
    )

# Key support highlight
TARGET = fibs["38%"]  # Example: 38.2% level as key support
fig.add_hline(
    y=TARGET,
    line_color="red",
    line_width=2,
    annotation_text=f"Major Support ~${TARGET:,.0f}",
    annotation_position="right"
)

fig.update_layout(
    height=650,
    template="plotly_dark",
    xaxis_title="Date",
    yaxis_title="Price (USD)"
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------
# Quant interpretation
# -------------------------
st.subheader("Quantitative Interpretation")

st.metric("Trend slope", f"{slope:.2f}")

if slope > 0:
    st.success("**Uptrend intact** → Fibonacci support is structurally valid.")
else:
    st.warning("Trend weakening → **Support level at risk.**")

st.write("### Fibonacci Levels")
st.json({k: round(v, 2) for k, v in fibs.items()})