"""Daily SET index history from the exchange's public website, index only."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

import numpy as np
import pandas as pd
from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException

logger = logging.getLogger(__name__)
ENDPOINT = 'https://www.set.or.th/api/set/index/SET/historical-trading'
OVERVIEW = 'https://www.set.or.th/en/market/index/set/overview'


def parse_set_history(payload, start, end, min_rows=220):
    rows = payload.get('historicalIndices')
    if not isinstance(rows, list) or not rows:
        raise ValueError('SET response contains no historicalIndices')
    if any(row.get('symbol') != 'SET' for row in rows):
        raise ValueError('Response contains a different index; expected SET only')
    data = pd.DataFrame(rows).rename(columns={
        'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close',
        'totalVolume': 'Volume'})
    required = ['Open', 'High', 'Low', 'Close']
    if not {'date', *required}.issubset(data.columns):
        raise ValueError('SET history is missing date or OHLC fields')
    dates = pd.to_datetime(data['date'], errors='coerce', utc=True)
    data.index = pd.DatetimeIndex(dates).tz_convert('Asia/Bangkok').tz_localize(None).normalize()
    data = data.loc[~data.index.isna()].sort_index()
    data = data.loc[~data.index.duplicated(keep='last')]
    data = data.loc[(data.index >= pd.Timestamp(start)) & (data.index <= pd.Timestamp(end))]
    data[required] = data[required].apply(pd.to_numeric, errors='coerce')
    valid = np.isfinite(data[required]).all(axis=1) & (data[required] > 0).all(axis=1)
    valid &= data['High'] >= data[['Open', 'Close', 'Low']].max(axis=1)
    valid &= data['Low'] <= data[['Open', 'Close', 'High']].min(axis=1)
    data = data.loc[valid]
    if len(data) < min_rows:
        raise ValueError(f'SET has {len(data)} valid sessions; need {min_rows}')
    if (pd.Timestamp(end) - data.index[-1]).days > 10:
        raise ValueError('SET history is stale (latest session more than 10 days old)')
    if 'Volume' in data:
        data['Volume'] = pd.to_numeric(data['Volume'], errors='coerce')
    columns = required + (['Volume'] if 'Volume' in data else [])
    data = data[columns].copy()
    data.index.name = 'Date'
    data.attrs['source'] = 'Stock Exchange of Thailand (set.or.th)'
    data.attrs['source_url'] = ENDPOINT
    return data


def fetch_set_index_history(min_rows=220, session=None):
    """Fetch completed daily SET sessions; no stock symbols are sent here.

    The website expects dd/MM/yyyy, NOT ISO dates. One calendar year normally
    supplies >220 Thai sessions, enough for SMA200 and its 20-session slope.
    """
    end = datetime.now(ZoneInfo('Asia/Bangkok')).date() - timedelta(days=1)
    start = end - timedelta(days=366)
    own_session = session is None
    session = session or requests.Session(impersonate="chrome")
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': OVERVIEW}
    try:
        last_error = None
        for attempt in range(2):
            try:
                response = session.get(ENDPOINT, params={
                    'fromDate': start.strftime('%d/%m/%Y'),
                    'toDate': end.strftime('%d/%m/%Y')}, headers=headers, timeout=20)
                response.raise_for_status()
                data = parse_set_history(response.json(), start, end, min_rows)
                logger.info('SET official: %d valid sessions, %s to %s', len(data), data.index[0].date(), data.index[-1].date())
                return data
            except (RequestException, ValueError, KeyError, TypeError) as exc:
                last_error = exc
                logger.warning('SET official fetch attempt %d: %s', attempt + 1, exc)
                if attempt == 0:
                    # Establish the normal website session before one retry.
                    try:
                        session.get(OVERVIEW, headers=headers, timeout=20)
                    except RequestException:
                        pass
        raise ValueError(f'Cannot obtain usable SET history: {last_error}')
    finally:
        if own_session:
            session.close()
