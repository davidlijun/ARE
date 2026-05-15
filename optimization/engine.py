import numpy as np
import pandas as pd
import torch
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from hmmlearn.hmm import GaussianHMM
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from scipy.stats import norm

class AnalyticalResearchEngine:
    def __init__(self, hmm_states=2, pca_components=3):
        # 1. Dimension Reduction & Regime Detection
        self.pca = PCA(n_components=pca_components)
        self.scaler = StandardScaler()
        self.hmm = GaussianHMM(n_components=hmm_states, covariance_type="full", n_iter=1000)
        
        # 2. NLP Sentiment (FinBERT)
        self.sent_model_name = "ProsusAI/finbert"
        self.tokenizer = AutoTokenizer.from_pretrained(self.sent_model_name)
        self.sent_model = AutoModelForSequenceClassification.from_pretrained(self.sent_model_name)

    # --- MODULE 1: FAST REGIME DETECTION ---
    def get_market_regime(self, macro_df):
        """
        Input: DF with features (VIX, Spreads, Returns, etc.)
        Output: Hidden State (0 or 1)
        """
        # Speed up: PCA reduction
        scaled_data = self.scaler.fit_transform(macro_df)
        pca_features = self.pca.fit_transform(scaled_data)
        
        # Fit and Predict
        self.hmm.fit(pca_features)
        states = self.hmm.predict(pca_features)
        current_state = states[-1]
        
        # Heuristic: Calculate mean return of state to identify 'Expansion' vs 'Contraction'
        return current_state

    # --- MODULE 2: LIQUIDITY MONITOR (VPIN) ---
    def get_vpin(self, trade_df, bucket_size=50000):
        """
        Detects 'Toxic' Informed Trading (VPIN > 0.4 usually signals danger)
        trade_df must have: ['price', 'volume', 'side' (buy/sell)]
        """
        trade_df['cum_vol'] = trade_df['volume'].cumsum()
        trade_df['bucket'] = (trade_df['cum_vol'] / bucket_size).astype(int)
        
        # Volume Imbalance
        vpin_series = trade_df.groupby('bucket').apply(
            lambda x: abs(x[x['side']=='buy']['volume'].sum() - x[x['side']=='sell']['volume'].sum())
        )
        
        current_vpin = (vpin_series.rolling(10).mean() / bucket_size).iloc[-1]
        return current_vpin

    # --- MODULE 3: OPTIONS RISK (GEX) ---
    def get_gamma_exposure(self, option_chain, spot_price):
        """
        Determines 'Stable' vs 'Acceleration' Regimes
        option_chain: DF with ['strike', 'type', 'openInterest', 'gamma']
        """
        # GEX Calculation (Standard Quant Approach)
        option_chain['GEX'] = option_chain['gamma'] * option_chain['openInterest'] * 100 * (spot_price**2) * 0.01
        
        # Market Makers are generally Short Puts, Long Calls
        option_chain.loc[option_chain['type'] == 'put', 'GEX'] *= -1
        
        total_gex = option_chain['GEX'].sum()
        regime = "POSITIVE_GAMMA (STABLE)" if total_gex > 0 else "NEGATIVE_GAMMA (ACCELERATION)"
        return total_gex, regime

    # --- MODULE 4: DYNAMIC RISK MANAGEMENT (ATR STOP) ---
    def get_atr_stop(self, price_df, n_atr=2.5, position='long'):
        """
        Volatility-Adjusted Exit Logic
        """
        high_low = price_df['high'] - price_df['low']
        high_close = np.abs(price_df['high'] - price_df['close'].shift())
        low_close = np.abs(price_df['low'] - price_df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        last_close = price_df['close'].iloc[-1]
        if position == 'long':
            return last_close - (n_atr * atr)
        else:
            return last_close + (n_atr * atr)

    # --- MODULE 5: MACO SENTIMENT (WARSH ANALYZER) ---
    def get_nlp_sentiment(self, text_list):
        """
        Analyze Fed-Speak or Weekend Headlines
        Returns: Average Sentiment Score [-1 to 1]
        """
        inputs = self.tokenizer(text_list, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            outputs = self.sent_model(**inputs)
        
        scores = torch.nn.functional.softmax(outputs.logits, dim=-1).numpy()
        # FinBERT labels: 0: positive, 1: negative, 2: neutral
        # Score calculation: Positive - Negative
        sentiment_score = scores[:, 0] - scores[:, 1]
        return np.mean(sentiment_score)

# --- EXECUTION BLOCK FOR MONDAY TEST ---
if __name__ == "__main__":
    are = AnalyticalResearchEngine()
    print("ARE Initialized. Ready for Monday US Session.")
    
    # Placeholder for Monday Workflow:
    # 1. Load US Market Data
    # 2. state = are.get_market_regime(data)
    # 3. gex, status = are.get_gamma_exposure(options, 742.0)
    # 4. print(f"Regime: {state} | GEX: {status}")