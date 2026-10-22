"""Yahoo downloads adapted from cookstock and set-thailand-screener-VCP.

Keep each symbol's real OHLC rows; a batch's union index is not its history.
"""
import logging
import time

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def clean_symbol_history(data, symbol):
    if data is None or data.empty:
        return pd.DataFrame()
    frame = data.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        for level in range(frame.columns.nlevels):
            if symbol in frame.columns.get_level_values(level):
                frame = frame.xs(symbol, axis=1, level=level).copy()
                break
        else:
            return pd.DataFrame()
    required = ['Open', 'High', 'Low', 'Close']
    if not set(required).issubset(frame.columns) or not isinstance(frame.index, pd.DatetimeIndex):
        return pd.DataFrame()
    frame = frame.loc[~frame.index.isna()]
    frame = frame.sort_index()
    frame = frame.loc[~frame.index.duplicated(keep='last')]
    frame[required] = frame[required].apply(pd.to_numeric, errors='coerce')
    frame = frame.loc[np.isfinite(frame[required]).all(axis=1)]
    frame = frame.loc[(frame[required] > 0).all(axis=1)]
    # Normalize daily dates without shifting a Thai session into another date.
    if frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)
    return frame


def download_histories(symbols, period='2y', chunk_size=75, pause_seconds=2):
    """Download daily OHLCV in chunks, retry once and return per-symbol frames.

    auto_adjust=False follows cookstock and preserves raw OHLC used by this
    scanner. The 2y window and ticker grouping follow the VCP repo.
    Never fill missing prices or substitute a different market index.
    """
    symbols = list(dict.fromkeys(symbols))
    if chunk_size < 1:
        raise ValueError('chunk_size must be positive')
    result = {}
    for offset in range(0, len(symbols), chunk_size):
        chunk = symbols[offset:offset + chunk_size]
        for attempt in range(2):
            try:
                data = yf.download(chunk, period=period, interval='1d',
                                   group_by='ticker', auto_adjust=False,
                                   threads=True, progress=False, timeout=20)
                for symbol in chunk:
                    frame = clean_symbol_history(data, symbol)
                    if not frame.empty:
                        result[symbol] = frame
                        logger.info('%s: downloaded %d valid daily OHLC rows (%s)', symbol, len(frame), period)
                if all(symbol in result for symbol in chunk):
                    break
            except Exception as exc:
                logger.warning('Yahoo download attempt %d failed: %s', attempt + 1, exc)
            if attempt == 0:
                time.sleep(pause_seconds)
        if offset + chunk_size < len(symbols):
            time.sleep(pause_seconds)
    return result
