from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from src.data.yfinance_history import clean_symbol_history, download_histories
from src.data.git_storage_fetcher import GitStorageFetcher


def frame(n=260):
    return pd.DataFrame({name: np.arange(n) + 100.0 for name in ['Open', 'High', 'Low', 'Close', 'Volume']}, index=pd.bdate_range('2025-01-01', periods=n))


@pytest.mark.parametrize('group_by', ['ticker', 'price'])
def test_batch_does_not_inflate_one_day_benchmark(group_by):
    stock = frame()
    benchmark = frame().iloc[-1:]
    batch = pd.concat({'PTT.BK': stock, '^SET.BK': benchmark}, axis=1)
    if group_by == 'price':
        batch = batch.swaplevel(axis=1)
    with patch('src.data.yfinance_history.yf.download', return_value=batch):
        out = download_histories(['PTT.BK', '^SET.BK'], pause_seconds=0)
    assert len(out['PTT.BK']) == 260
    assert len(out['^SET.BK']) == 1


def test_flat_columns_and_invalid_prices():
    data = frame(5)
    data.loc[data.index[0], 'Close'] = np.nan
    data.loc[data.index[1], 'Open'] = np.inf
    data.loc[data.index[2], 'Low'] = 0
    assert len(clean_symbol_history(data, 'PTT.BK')) == 2


def test_fetcher_uses_download_two_years(tmp_path):
    batch = pd.concat({'PTT.BK': frame()}, axis=1)
    with patch('src.data.yfinance_history.yf.download', return_value=batch) as download:
        out = GitStorageFetcher(str(tmp_path)).fetch_price_fresh('PTT.BK')
    assert len(out) >= 200
    assert download.call_args.kwargs['period'] == '2y'
    assert download.call_args.kwargs['auto_adjust'] is False


def test_retry_and_chunks():
    with patch('src.data.yfinance_history.yf.download', side_effect=[RuntimeError('temporary'), frame(), frame()]) as download:
        out = download_histories(['A.BK', 'B.BK'], chunk_size=1, pause_seconds=0)
    assert set(out) == {'A.BK', 'B.BK'}
    assert download.call_count == 3


def test_missing_symbol_is_not_replaced():
    batch = pd.concat({'PTT.BK': frame()}, axis=1)
    assert clean_symbol_history(batch, '^SET.BK').empty
