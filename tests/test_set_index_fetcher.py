from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import Mock
import pandas as pd
import pytest
from src.data.set_index_fetcher import fetch_set_index_history, parse_set_history


def payload(n=241):
    dates = pd.bdate_range(end='2026-10-21', periods=n)
    return {'historicalIndices': [dict(date=str(d.date())+'T00:00:00+07:00', symbol='SET', open=1500, high=1510, low=1490, close=1505, totalVolume=10000) for d in dates[::-1]]}


def test_parse_official_ohlcv_sorted_and_sma_ready():
    frame = parse_set_history(payload(), date(2025, 1, 1), date(2026, 10, 21))
    assert len(frame) == 241
    assert frame.index.is_monotonic_increasing and frame.index.is_unique
    assert frame.index.tz is None
    assert frame.Close.rolling(200).mean().notna().sum() == 42
    assert 'set.or.th' in frame.attrs['source']


@pytest.mark.parametrize('bad', ['short', 'wrong_index', 'invalid_ohlc', 'stale'])
def test_reject_unusable_data(bad):
    data = payload(10 if bad == 'short' else 241)
    end = date(2026, 10, 21)
    if bad == 'wrong_index':
        data['historicalIndices'][0]['symbol'] = 'SET50'
    if bad == 'invalid_ohlc':
        for row in data['historicalIndices']:
            row['high'] = 1
    if bad == 'stale':
        end = date(2026, 11, 15)
    with pytest.raises(ValueError):
        parse_set_history(data, date(2025, 1, 1), end)


def test_request_uses_dd_mm_yyyy_and_set_endpoint():
    session = Mock()
    response = session.get.return_value
    # Keep test independent of the day when CI is run.
    dates = pd.bdate_range(end=datetime.now(ZoneInfo('Asia/Bangkok')).date()-timedelta(days=1), periods=241)
    data = payload()
    for row, d in zip(data['historicalIndices'], dates[::-1]):
        row['date'] = str(d.date())+'T00:00:00+07:00'
    response.json.return_value = data
    frame = fetch_set_index_history(session=session)
    assert len(frame) >= 220
    call = session.get.call_args
    assert '/index/SET/' in call.args[0]
    assert len(call.kwargs['params']['fromDate'].split('/')) == 3
