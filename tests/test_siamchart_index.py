from datetime import date
from io import BytesIO
from zipfile import ZipFile
import numpy as np
import pandas as pd
import pytest
from src.data.siamchart_index import parse_archive, validate_history
from src.screening.benchmark import analyze_spy_trend, calculate_market_breadth, format_benchmark_summary
from src.screening.phase_indicators import classify_phase, calculate_relative_strength


def frame(n):
    values = np.linspace(1000, 1500, n)
    return pd.DataFrame(dict(Open=values, High=values+5, Low=values-5, Close=values, Volume=1000), index=pd.bdate_range(end='2026-10-21', periods=n))


def test_archive_extracts_set_not_stocks_or_other_index():
    buf=BytesIO()
    with ZipFile(buf, 'w') as archive:
        archive.writestr('day.csv', '<TICKER>,<DTYYYYMMDD>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>\nSET,20261021,100,110,90,105,1000\nSET50,20261021,50,60,40,55,500\nPTT,20261021,30,31,29,30,100')
    result=parse_archive(buf.getvalue())
    assert len(result) == 1 and result.Close.iloc[0] == 105


def test_194_proxy_is_real_mean_not_padded_sma200():
    data=frame(194)
    a=analyze_spy_trend(data, data.Close.iloc[-1])
    assert a['long_ma_period'] == 194 and a['long_ma_is_proxy']
    assert a['sma_200'] == round(data.Close.mean(), 2)
    assert a['slope_200'] is None
    report=format_benchmark_summary(a, calculate_market_breadth([]))
    assert '194 SMA proxy for SMA200' in report and 'slope: N/A' in report
    # This permission applies to the benchmark, not individual stocks.
    assert classify_phase(data, data.Close.iloc[-1])['phase'] == 0
    assert calculate_relative_strength(data.Close, data.Close).notna().sum() == 194


def test_switches_to_genuine_sma200_when_enough_actual_rows():
    data=frame(220)
    a=analyze_spy_trend(data, data.Close.iloc[-1])
    assert not a['long_ma_is_proxy'] and a['long_ma_period'] == 200
    assert a['sma_200'] == round(data.Close.tail(200).mean(), 2)
    assert a['slope_200'] is not None


def test_reject_less_than_194_and_stale():
    with pytest.raises(ValueError):validate_history(frame(193), date(2026,10,21))
    with pytest.raises(ValueError):validate_history(frame(194), date(2026,11,21))
    assert len(validate_history(frame(194),date(2026,10,21))) == 194
