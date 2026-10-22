"""SET-only OHLCV extracted from SiamChart's published current-year EOD ZIP."""
import csv
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from curl_cffi import requests

URL = 'https://siamchart.com/downloads/set-archive_EOD.zip'
CACHE = Path('data/benchmark_cache/SET_siamchart.csv')
COLUMNS = ['Open', 'High', 'Low', 'Close', 'Volume']


def parse_archive(content):
    if len(content) > 25_000_000:
        raise ValueError('SiamChart archive exceeds size limit')
    rows = []
    with ZipFile(BytesIO(content)) as archive:
        members = [m for m in archive.infolist() if m.filename.endswith('.csv')]
        if len(members) > 400 or sum(m.file_size for m in members) > 100_000_000:
            raise ValueError('Unexpected EOD archive size')
        for member in members:
            if member.file_size > 1_000_000:
                raise ValueError('Unexpected EOD member size')
            for row in csv.DictReader(archive.read(member).decode('utf-8-sig').splitlines()):
                if row.get('<TICKER>') == 'SET':
                    rows.append([row['<DTYYYYMMDD>']] + [row[key] for key in
                                 ['<OPEN>', '<HIGH>', '<LOW>', '<CLOSE>', '<VOL>']])
    if not rows:
        raise ValueError('No SET index rows in SiamChart archive')
    frame = pd.DataFrame(rows, columns=['Date'] + COLUMNS)
    frame['Date'] = pd.to_datetime(frame['Date'], format='%Y%m%d', errors='coerce')
    frame[COLUMNS] = frame[COLUMNS].apply(pd.to_numeric, errors='coerce')
    return frame.set_index('Date')


def validate_history(frame, end, min_rows=194):
    frame = frame.copy()
    if not isinstance(frame.index, pd.DatetimeIndex) or not set(COLUMNS).issubset(frame.columns):
        raise ValueError('Invalid SET index history schema')
    frame = frame.loc[~frame.index.isna()].sort_index()
    frame = frame.loc[~frame.index.duplicated(keep='last')]
    frame = frame.loc[frame.index <= pd.Timestamp(end), COLUMNS]
    frame = frame.apply(pd.to_numeric, errors='coerce')
    ohlc = frame[COLUMNS[:4]]
    valid = np.isfinite(ohlc).all(axis=1) & (ohlc > 0).all(axis=1)
    valid &= frame.High >= frame[['Open', 'Low', 'Close']].max(axis=1)
    valid &= frame.Low <= frame[['Open', 'High', 'Close']].min(axis=1)
    frame = frame.loc[valid]
    if len(frame) < min_rows:
        raise ValueError(f'SiamChart SET: {len(frame)} valid days; need {min_rows}')
    if (pd.Timestamp(end) - frame.index[-1]).days > 10:
        raise ValueError('SiamChart SET history is stale')
    frame.index.name = 'Date'
    frame.attrs['source'] = 'SiamChart (SET index only)'
    frame.attrs['source_url'] = URL
    return frame


def fetch_siamchart_index(cache_path=CACHE):
    end = datetime.now(ZoneInfo('Asia/Bangkok')).date() - timedelta(days=1)
    response = requests.get(URL, impersonate='chrome', timeout=30)
    response.raise_for_status()
    fresh = parse_archive(response.content)
    cache_path = Path(cache_path)
    # Persist actual observations across year-end; never generate missing dates.
    if cache_path.exists():
        cached = pd.read_csv(cache_path, index_col='Date', parse_dates=['Date'])
        fresh = pd.concat([cached, fresh])
    history = validate_history(fresh, end).tail(400)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(cache_path)
    return history
