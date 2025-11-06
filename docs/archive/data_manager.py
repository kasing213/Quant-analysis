"""
Enhanced Data Manager
Combines IB data with fallback to yfinance, plus data caching and management
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
import yfinance as yf
import logging
from pathlib import Path
import pickle

from .ib_client import create_ib_client
from .dataproc import clean_prices, compute_returns

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, use_ib_for_data=False, use_ib_for_trading=True, paper_trading=True, cache_dir="data_cache"):
        # Dual API Strategy: yfinance for data, IB for trading only
        self.use_ib_for_data = use_ib_for_data  # Default False - use yfinance for historical data
        self.use_ib_for_trading = use_ib_for_trading  # Keep IB for trading operations
        self.paper_trading = paper_trading
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ib_client = None
        self._connection_attempts = 0
        self.max_connection_attempts = 1
        self._last_attempt_time = None
        self._retry_cooldown = 300  # 5 minutes between retry attempts

    async def _get_ib_client(self):
        """Get or create IB client - only for trading operations in dual API strategy"""
        if self.ib_client and self.ib_client.connected:
            return self.ib_client

        # Only connect IB if needed for trading operations
        if not self.use_ib_for_trading:
            return None

        # Check cooldown period
        now = datetime.now()
        if (self._last_attempt_time and
            (now - self._last_attempt_time).total_seconds() < self._retry_cooldown):
            return None

        if self._connection_attempts >= self.max_connection_attempts:
            logger.info("IB not available for trading operations")
            self.use_ib_for_trading = False
            return None

        try:
            self._connection_attempts += 1
            self._last_attempt_time = now
            self.ib_client = await create_ib_client(self.paper_trading)
            if self.ib_client.connected:
                self._connection_attempts = 0  # Reset on successful connection
                logger.info("Successfully connected to Interactive Brokers for trading")
                return self.ib_client
        except Exception as e:
            logger.debug(f"IB connection attempt {self._connection_attempts} failed: {e}")

        return None

    def _get_cache_path(self, symbol: str, data_type: str, period: str = None) -> Path:
        """Generate cache file path"""
        cache_name = f"{symbol}_{data_type}"
        if period:
            cache_name += f"_{period}"
        cache_name += ".pkl"
        return self.cache_dir / cache_name

    def _load_cache(self, cache_path: Path, max_age_hours: int = 24) -> Optional[pd.DataFrame]:
        """Load cached data if it exists and is recent"""
        if not cache_path.exists():
            return None

        try:
            # Check file age
            file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            if file_age > timedelta(hours=max_age_hours):
                return None

            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
                logger.info(f"Loaded cached data from {cache_path}")
                return data
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_path}: {e}")
            return None

    def _save_cache(self, data: pd.DataFrame, cache_path: Path):
        """Save data to cache"""
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Cached data to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_path}: {e}")

    async def get_price_data(self, symbol: str, start_date: str = None, end_date: str = None,
                           period: str = "1y", use_cache: bool = True) -> pd.DataFrame:
        """
        Get price data - DUAL API STRATEGY: yfinance primary for historical data, IB for trading only
        Returns DataFrame with Date index and 'price' column
        """
        cache_path = self._get_cache_path(symbol, "price", period)

        # Try cache first if enabled
        if use_cache:
            cached_data = self._load_cache(cache_path, max_age_hours=1)  # 1 hour for price data
            if cached_data is not None:
                return cached_data

        # DUAL API STRATEGY: Use yfinance as primary for historical data (fast and reliable)
        # Only try IB for historical data if explicitly requested
        if self.use_ib_for_data:
            ib_data = await self._get_ib_price_data(symbol, start_date, end_date, period)
            if ib_data is not None and not ib_data.empty:
                # Cache and return
                if use_cache:
                    self._save_cache(ib_data, cache_path)
                return ib_data

        # Primary: yfinance for historical data (reliable, fast, no connection issues)
        logger.info(f"Using yfinance for historical data: {symbol}")
        yf_data = self._get_yfinance_data(symbol, start_date, end_date, period)

        if use_cache and not yf_data.empty:
            self._save_cache(yf_data, cache_path)

        return yf_data

    async def _get_ib_price_data(self, symbol: str, start_date: str = None,
                               end_date: str = None, period: str = "1y") -> Optional[pd.DataFrame]:
        """Get price data from Interactive Brokers"""
        try:
            client = await self._get_ib_client()
            if not client:
                return None

            # Convert period to IB format
            ib_period = self._convert_period_to_ib(period)

            hist_data = await client.get_historical_data(symbol, ib_period, '1 day')

            if hist_data.empty:
                return None

            # Convert to our standard format
            price_df = hist_data[['close']].copy()
            price_df.columns = ['price']
            price_df.index.name = 'Date'

            return clean_prices(price_df)

        except Exception as e:
            logger.warning(f"Failed to get IB data for {symbol}: {e}")
            return None

    def _get_yfinance_data(self, symbol: str, start_date: str = None,
                         end_date: str = None, period: str = "1y") -> pd.DataFrame:
        """Get price data from yfinance (fallback)"""
        try:
            if start_date and end_date:
                df = yf.download(symbol, start=start_date, end=end_date, auto_adjust=True, progress=False)
            else:
                df = yf.download(symbol, period=period, auto_adjust=True, progress=False)

            if df.empty:
                return pd.DataFrame({"price": []}, index=pd.DatetimeIndex([], name="Date"))

            # Handle multi-index columns
            if isinstance(df.columns, pd.MultiIndex):
                close_col = df['Close']
                if isinstance(close_col, pd.DataFrame):
                    close_col = close_col.iloc[:, 0]
            else:
                close_col = df['Close']

            price_df = close_col.to_frame()
            price_df.columns = ['price']
            price_df.index.name = 'Date'

            return clean_prices(price_df.dropna())

        except Exception as e:
            logger.error(f"Failed to get yfinance data for {symbol}: {e}")
            return pd.DataFrame({"price": []}, index=pd.DatetimeIndex([], name="Date"))

    async def get_real_time_price(self, symbol: str) -> Optional[Dict]:
        """Get real-time price - DUAL API: yfinance primary, IB for trading when available"""
        # For real-time pricing, try IB first only if connected for trading
        if self.use_ib_for_trading:
            try:
                client = await self._get_ib_client()
                if client:
                    return await client.get_market_data(symbol)
            except Exception as e:
                logger.debug(f"Failed to get real-time data from IB for {symbol}: {e}")

        # Fallback: get latest price from yfinance
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Try multiple price sources from yfinance
            price = (
                info.get('regularMarketPrice') or
                info.get('currentPrice') or
                info.get('previousClose') or
                info.get('ask') or
                info.get('bid')
            )

            if price and price > 0:  # Ensure price is valid and positive
                return {
                    'symbol': symbol,
                    'last': float(price),
                    'bid': float(info.get('bid', 0)) if info.get('bid') else None,
                    'ask': float(info.get('ask', 0)) if info.get('ask') else None,
                    'volume': info.get('regularMarketVolume') or info.get('volume'),
                    'timestamp': datetime.now()
                }
            else:
                # If info fails, try historical data for latest price
                hist = ticker.history(period="1d")
                if not hist.empty:
                    latest_price = hist['Close'].iloc[-1]
                    if latest_price > 0:
                        return {
                            'symbol': symbol,
                            'last': float(latest_price),
                            'bid': None,
                            'ask': None,
                            'volume': int(hist['Volume'].iloc[-1]) if 'Volume' in hist else None,
                            'timestamp': datetime.now()
                        }

        except Exception as e:
            logger.error(f"Failed to get real-time price for {symbol}: {e}")

        return None

    async def get_multiple_stocks_data(self, symbols: List[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
        """Get price data for multiple stocks efficiently"""
        results = {}

        # Process stocks concurrently if using IB
        if self.use_ib:
            tasks = [self.get_price_data(symbol, period=period) for symbol in symbols]
            data_list = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, data in zip(symbols, data_list):
                if isinstance(data, Exception):
                    logger.error(f"Error getting data for {symbol}: {data}")
                    results[symbol] = pd.DataFrame()
                else:
                    results[symbol] = data
        else:
            # Process sequentially with yfinance
            for symbol in symbols:
                results[symbol] = await self.get_price_data(symbol, period=period)

        return results

    def _convert_period_to_ib(self, period: str) -> str:
        """Convert standard period format to IB format"""
        period_map = {
            '1d': '1 D',
            '5d': '5 D',
            '1mo': '1 M',
            '3mo': '3 M',
            '6mo': '6 M',
            '1y': '1 Y',
            '2y': '2 Y',
            '5y': '5 Y',
            '10y': '10 Y'
        }
        return period_map.get(period, '1 Y')

    async def get_portfolio_data(self) -> Dict:
        """Get current portfolio data from IB"""
        if not self.use_ib:
            return {'positions': [], 'account_info': {}}

        try:
            client = await self._get_ib_client()
            if not client:
                return {'positions': [], 'account_info': {}}

            portfolio = client.get_portfolio()
            account_info = client.get_account_info()

            return {
                'positions': portfolio,
                'account_info': account_info,
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"Failed to get portfolio data: {e}")
            return {'positions': [], 'account_info': {}}

    async def health_check(self) -> Dict[str, Any]:
        """Monitor both API connections as per quant-claude.md dual API strategy"""
        status = {
            'yahoo_finance': True,  # Always available
            'interactive_brokers_trading': False,
            'interactive_brokers_data': False,
            'timestamp': datetime.now().isoformat(),
            'strategy': 'dual_api_yfinance_primary'
        }

        # Check IB connection if enabled
        if self.use_ib_for_trading or self.use_ib_for_data:
            try:
                client = await self._get_ib_client()
                if client and client.connected:
                    status['interactive_brokers_trading'] = self.use_ib_for_trading
                    status['interactive_brokers_data'] = self.use_ib_for_data
            except Exception as e:
                logger.debug(f"IB health check failed: {e}")

        return status

    async def close_connections(self):
        """Clean up connections"""
        if self.ib_client and self.ib_client.connected:
            self.ib_client.disconnect()

# Utility functions for Streamlit integration
def sync_get_price_data(symbol: str, period: str = "1y", use_ib: bool = True) -> pd.DataFrame:
    """Synchronous wrapper for Streamlit"""
    data_manager = DataManager(use_ib=use_ib)
    try:
        return asyncio.run(data_manager.get_price_data(symbol, period=period))
    finally:
        asyncio.run(data_manager.close_connections())

def sync_get_real_time_price(symbol: str, use_ib_for_data: bool = False, use_ib_for_trading: bool = False) -> Optional[Dict]:
    """Synchronous wrapper for real-time price - Dual API strategy"""
    data_manager = DataManager(use_ib_for_data=use_ib_for_data, use_ib_for_trading=use_ib_for_trading)
    try:
        return asyncio.run(data_manager.get_real_time_price(symbol))
    finally:
        asyncio.run(data_manager.close_connections())

def sync_get_multiple_stocks(symbols: List[str], period: str = "1y", use_ib_for_data: bool = False) -> Dict[str, pd.DataFrame]:
    """Synchronous wrapper for multiple stocks - Dual API strategy"""
    data_manager = DataManager(use_ib_for_data=use_ib_for_data, use_ib_for_trading=False)
    try:
        return asyncio.run(data_manager.get_multiple_stocks_data(symbols, period))
    finally:
        asyncio.run(data_manager.close_connections())