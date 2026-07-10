"""Fetch and maintain the universe of Thai SET-listed stocks.

This module fetches all active SET and mai stocks from the TradingView scanner API.
It automatically filters out warrants, DWs, and funds to focus on common stocks,
and appends the '.BK' suffix required by yfinance.
"""

import logging
import pickle
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# yfinance requires this suffix for SET-listed tickers
SET_SUFFIX = ".BK"


class USStockUniverseFetcher:
    """Fetches and maintains the universe of all SET-listed Thai stocks.

    Class name kept as USStockUniverseFetcher so the rest of the codebase
    does not need to change its imports. Internally it now fetches all Thai SET tickers.
    """

    def __init__(self, cache_dir: str = "./data/cache"):
        """Initialize the universe fetcher.

        Args:
            cache_dir: Directory for caching universe data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "thai_all_stock_universe.pkl"
        logger.info("USStockUniverseFetcher initialized (Thai ALL STOCKS mode via TradingView)")

    def _fetch_all_set_symbols(self) -> pd.DataFrame:
        """Fetch all Thai stocks from TradingView Scanner API.

        Returns:
            DataFrame with columns ['symbol', 'name']
        """
        url = "https://scanner.tradingview.com/thailand/scan"
        payload = {
            "columns": ["name", "type", "subtype"],
            "range": [0, 5000] # Set high enough to catch all ~800+ stocks
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info("Fetching stock list from TradingView API...")
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            symbols = []
            for item in data.get('data', []):
                ticker_data = item.get('d', [])
                if len(ticker_data) >= 2:
                    ticker = ticker_data[0]
                    asset_type = ticker_data[1]
                    
                    # กรองเอาเฉพาะหุ้นสามัญ (stock) ตัดพวก Warrant, DW ออก
                    if asset_type == 'stock':
                        symbols.append({
                            "symbol": f"{ticker}{SET_SUFFIX}", 
                            "name": ticker
                        })
            
            df = pd.DataFrame(symbols)
            logger.info(f"Successfully fetched {len(df)} Thai stocks.")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching symbols from TradingView: {e}")
            return pd.DataFrame()

    def fetch_universe(self, force_refresh: bool = False) -> List[str]:
        """Fetch the universe of all Thai stocks.

        Args:
            force_refresh: Force refresh even if cached data is recent

        Returns:
            List of stock ticker symbols (with .BK suffix)
        """
        # Check cache
        if not force_refresh and self.cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(
                self.cache_file.stat().st_mtime
            )

            if cache_age < timedelta(days=1):
                logger.info("Loading universe from cache")
                with open(self.cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                logger.info(f"Loaded {len(cached_data['symbols'])} symbols from cache")
                return cached_data['symbols']

        logger.info("Building SET full universe...")

        all_stocks = self._fetch_all_set_symbols()

        if all_stocks.empty:
            logger.error("Failed to build SET universe. Check network or API.")
            return []

        # Remove duplicates, sort
        all_stocks = all_stocks.drop_duplicates(subset=['symbol'])
        all_stocks = all_stocks.sort_values('symbol').reset_index(drop=True)

        symbols = all_stocks['symbol'].tolist()

        # Cache the results
        cache_data = {
            'symbols': symbols,
            'fetch_date': datetime.now().isoformat(),
            'count': len(symbols),
            'metadata': {
                'source': 'TradingView Scanner API',
                'filtered_count': len(symbols)
            }
        }

        with open(self.cache_file, 'wb') as f:
            pickle.dump(cache_data, f)

        logger.info(f"Cached {len(symbols)} symbols")
        logger.info(f"Universe composition: {cache_data['metadata']}")

        return symbols

    def get_universe_info(self) -> Dict:
        """Get information about the cached universe.

        Returns:
            Dict with universe metadata
        """
        if not self.cache_file.exists():
            return {
                'cached': False,
                'count': 0
            }

        with open(self.cache_file, 'rb') as f:
            cached_data = pickle.load(f)

        cache_age = datetime.now() - datetime.fromtimestamp(
            self.cache_file.stat().st_mtime
        )

        return {
            'cached': True,
            'count': cached_data['count'],
            'fetch_date': cached_data['fetch_date'],
            'cache_age_hours': cache_age.total_seconds() / 3600,
            'metadata': cached_data.get('metadata', {})
        }
