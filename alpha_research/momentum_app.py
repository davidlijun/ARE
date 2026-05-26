import streamlit as st
from momentum_engine import MomentumEngine

st.set_page_config(page_title="Global Momentum Dashboard", layout="wide")

st.title("🚀 ACWI/S&P 500 Momentum Manager")
st.sidebar.header("Settings")

# 1. Universe Selection
universe_type = st.sidebar.selectbox("Select Universe", ["S&P 500", "ACWI Tech"])
cash_to_deploy = st.sidebar.number_input("Capital to Deploy ($)", value=1600)

# Mock ticker list (In production, pull from Wikipedia or a CSV)
if universe_type == "S&P 500":
    tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'LLY', 'AVGO', 'VRT', 'COST']
else:
    tickers = ['TSM', 'ASML', 'SAP', 'TM', 'SNY', 'ARM']

# 2. Execution
engine = MomentumEngine(tickers)

if st.button("Run Momentum Analysis"):
    with st.spinner("Analyzing Factor Loadings..."):
        raw_data = engine.get_data()
        scores = engine.calculate_momentum(raw_data)
        
        # UI Layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Top Momentum Ranks")
            st.dataframe(scores.head(10).rename("Momentum Score"))
            
        with col2:
            st.subheader(f"Deployment Plan for ${cash_to_deploy}")
            top_5 = scores.head(5).index.tolist()
            allocation = cash_to_deploy / 5
            
            for ticker in top_5:
                st.success(f"Buy **{ticker}**: ${allocation:.2f}")

        # 3. Risk Chart
        st.subheader("Relative Performance (Last 6 Months)")
        normalized_df = raw_data[top_5] / raw_data[top_5].iloc[0]
        st.line_chart(normalized_df)

st.info("Note: This dashboard uses Risk-Adjusted Momentum to ensure 'Persistent' growth.")