"""Fetch and maintain the universe of Thai SET-listed stocks.

This module maintains a curated universe of SET50 (Stock Exchange of Thailand)
stocks for screening. Since Thailand's exchange does not offer a free public
FTP feed like NASDAQ, the universe is maintained as a curated list that you
update manually twice a year when SET revises SET50 (each January and July).
"""

import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Curated SET50 constituent list (base symbols, without .BK suffix).
# Source: SET official constituents list / Wikipedia, as of 2025-2026 revision.
# NOTE: SET revises SET50 twice a year (effective Jan 1 and Jul 1).
# Update this list from https://www.set.or.th/en/market/index/set50/overview
# when a new revision is announced.
SET50_SYMBOLS: Dict[str, str] = {
    "ADVANC": "Advanced Info Service",
    "AOT": "Airports of Thailand",
    "AWC": "Asset World Corp",
    "BANPU": "Banpu",
    "BBL": "Bangkok Bank",
    "BCP": "Bangchak Corporation",
    "BDMS": "Bangkok Dusit Medical Service",
    "BEM": "Bangkok Expressway and Metro",
    "BH": "Bumrungrad International Hospital",
    "BJC": "Berli Jucker",
    "BTS": "BTS Group Holdings",
    "CBG": "Carabao Group",
    "CCET": "Cal-Comp Electronics (Thailand)",
    "COM7": "Com Seven",
    "CPALL": "CP All",
    "CPF": "Charoen Pokphand Foods",
    "CPN": "Central Pattana",
    "CRC": "Central Retail Corporation",
    "DELTA": "Delta Electronics (Thailand)",
    "EGCO": "Electricity Generating",
    "GPSC": "Global Power Synergy",
    "GULF": "Gulf Development",
    "HMPRO": "Home Product Center",
    "IVL": "Indorama Ventures",
    "KBANK": "Kasikornbank",
    "KCE": "KCE Electronics",
    "KKP": "Kiatnakin Phatra Bank",
    "KTB": "Krungthai Bank",
    "KTC": "Krungthai Card",
    "LH": "Land and Houses",
    "MINT": "Minor International",
    "MTC": "Muangthai Capital",
    "OR": "PTT Oil and Retail Business",
    "OSP": "Osotspa",
    "PTT": "PTT",
    "PTTEP": "PTT Exploration and Production",
    "PTTGC": "PTT Global Chemical",
    "RATCH": "Ratch Group",
    "SCB": "Siam Commercial Bank",
    "SCC": "Siam Cement Group",
    "SCGP": "SCG Packaging",
    "TCAP": "Thanachart Capital",
    "TIDLOR": "Tidlor Holdings",
    "TISCO": "Tisco Financial Group",
    "TLI": "Thai Life Insurance",
    "TOP": "Thai Oil",
    "TRUE": "TRUE Corporation",
    "TTB": "TMBThanachart Bank",
    "TU": "Thai Union Group",
    "VGI": "VGI",
    "WHA": "WHA Corporation",
}

# yfinance requires this suffix for SET-listed tickers
SET_SUFFIX = ".BK"


class USStockUniverseFetcher:
    """Fetches and maintains the universe of SET50-listed Thai stocks.

    Class name kept as USStockUniverseFetcher so the rest of the codebase
    (fetcher.py, run_optimized_scan.py, etc.) does not need to change its
    imports. Internally it now returns Thai SET tickers instead of US ones.
    """

    def __init__(self, cache_dir: str = "./data/cache"):
        """Initialize the universe fetcher.

        Args:
            cache_dir: Directory for caching universe data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "thai_stock_universe.pkl"
        logger.info("USStockUniverseFetcher initialized (Thai SET50 mode)")

    def _build_set50_dataframe(self) -> pd.DataFrame:
        """Build a DataFrame of SET50 stocks with .BK suffix applied.

        Returns:
            DataFrame with columns ['symbol', 'name']
        """
        rows = [
            {"symbol": f"{symbol}{SET_SUFFIX}", "name": name}
            for symbol, name in SET50_SYMBOLS.items()
        ]
        df = pd.DataFrame(rows)
        logger.info(f"Built SET50 universe with {len(df)} stocks")
        return df

    def fetch_universe(self, force_refresh: bool = False) -> List[str]:
        """Fetch the universe of SET50-listed Thai stocks.

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

        logger.info("Building SET50 universe...")

        all_stocks = self._build_set50_dataframe()

        if all_stocks.empty:
            logger.error("Failed to build SET50 universe")
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
                'source': 'SET50 curated list',
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
