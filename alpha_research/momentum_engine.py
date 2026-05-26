import yfinance as yf
import pandas as pd
import numpy as np
from requests import Session

class MomentumEngine:
    def __init__(self, tickers):
        # Do not set a custom requests Session for yfinance — let yfinance manage its session
        self.tickers = tickers

    def get_data(self):
        # Do not pass a session to yf.download to avoid YFDataException
        data = yf.download(self.tickers, period="2y", progress=False)['Close']
        return data

    def calculate_momentum(self, df):
        """
        Calculates Risk-Adjusted Momentum: 
        (12-month return - 1-month return) / 12-month Volatility
        """
        # 1. Total Return (excluding the most recent month to avoid 'reversal' effect)
        df = df.dropna()
        df = df[df.columns.intersection(self.tickers)]  # Ensure we only use the specified tickers  

        
        # Calculate momentum signal
   
        returns_12m = df.pct_change(252)
        returns_1m = df.pct_change(21)

        momentum_signal = returns_12m - returns_1m

        # 2. Volatility (Standard Deviation of daily returns)
        volatility = df.pct_change().rolling(252).std() * np.sqrt(252)
        
        # 3. Risk-Adjusted Score
        score = momentum_signal / volatility
        return score.iloc[-1].sort_values(ascending=False)