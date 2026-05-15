"""
Data utilities for ARE dashboard - consolidated yfinance data fetching.
Provides cached functions for various data types and timeframes.
"""
import os
import streamlit as st
import pandas as pd
import appdirs as ad
from pathlib import Path
import yfinance as yf
# Create a valid path in your Windows Temp directory
cache_path = os.path.join(os.environ['TEMP'], 'yfinance') if os.name == 'nt' else ad.user_cache_dir("yfinance")
if not os.path.exists(cache_path):
    os.makedirs(cache_path)

yf.set_tz_cache_location(cache_path)

@st.cache_data(ttl=3600)
def get_daily_returns(tickers, benchmark, start_date):
    """
    Fetch daily price data and return percentage changes.
    
    Args:
        tickers: List of ticker symbols
        benchmark: Benchmark ticker
        start_date: Start date string (e.g., '2020-01-01')
    
    Returns:
        DataFrame of daily returns
    """
    all_tickers = list(set(tickers + [benchmark]))
    data = yf.download(all_tickers, start=start_date, auto_adjust=True, progress=False)['Close']
    return data.pct_change(fill_method=None).dropna()


@st.cache_data(ttl=3600)
def get_price_history(tickers, period="2y", interval="1d"):
    """
    Fetch price history for technical analysis.
    
    Args:
        tickers: List of ticker symbols
        period: Time period (e.g., '2y', '1y', '3mo')
        interval: Data interval ('1d', '1wk', '1mo')
    
    Returns:
        DataFrame of closing prices
    """
    data = yf.download(tickers, period=period, interval=interval, auto_adjust=True, progress=False)['Close']
    return data


@st.cache_data(ttl=3600)
def get_price_history_with_benchmark(tickers, benchmark, period="2y", interval="1d"):
    """
    Fetch price history including benchmark for RS analysis.
    
    Args:
        tickers: List of ticker symbols
        benchmark: Benchmark ticker
        period: Time period (e.g., '2y', '1y', '3mo')
        interval: Data interval ('1d', '1wk', '1mo')
    
    Returns:
        DataFrame of closing prices including benchmark
    """
    all_tickers = tickers + [benchmark]
    data = yf.download(all_tickers, period=period, interval=interval, auto_adjust=True, progress=False)['Close']
    return data


@st.cache_data(ttl=600)
def get_premarket_data(tickers):
    """
    Fetch 1-minute intraday data with extended hours for pre-market gap analysis.
    
    Args:
        tickers: List of ticker symbols
    
    Returns:
        Tuple of (intraday_data, daily_history) or None on error
    """
    if not tickers:
        return None, None
    
    try:
        # 1-minute data with pre/post market
        intraday = yf.download(tickers, period="1d", interval="1m", prepost=True, progress=False)
        
        # 2-day daily data for previous close
        history = yf.download(tickers, period="2d", interval="1d", progress=False)['Close']
        
        return intraday, history
    except Exception:
        return None, None


@st.cache_data(ttl=60)
def get_live_intraday(tickers, period="2d"):
    """
    Fetch live intraday minute data for real-time monitoring.
    Refreshes every 60 seconds.
    
    Args:
        tickers: List of ticker symbols
        period: Time period for data (default '2d')
    
    Returns:
        DataFrame of 1-minute interval closing prices
    """
    if not tickers:
        return None
    
    try:
        data = yf.download(tickers, period=period, interval="1m", progress=False)['Close']
        return data
    except Exception:
        return None
