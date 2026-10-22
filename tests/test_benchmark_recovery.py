"""Regression coverage for truncated Yahoo benchmark responses."""
from unittest.mock import Mock, patch
import numpy as np
import pandas as pd
from src.screening.optimized_batch_processor import OptimizedBatchProcessor
from src.screening.benchmark import analyze_spy_trend, calculate_market_breadth, format_benchmark_summary, should_generate_signals
from run_optimized_scan import save_report


def history(n):
    close = np.linspace(1000, 1500, n)
    return pd.DataFrame({'Close': close, 'High': close + 5, 'Low': close - 5,
                         'Volume': np.full(n, 1000000)},
                        index=pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n))


def processor(frame):
    obj = OptimizedBatchProcessor.__new__(OptimizedBatchProcessor)
    obj.use_git_storage = True
    obj.git_fetcher = Mock()
    obj.git_fetcher.fetch_price_fresh.return_value = frame
    obj.spy_data = obj.spy_price = None
    return obj


def test_truncated_yahoo_recovers_from_siamchart_set_only():
    obj = processor(history(1))
    official = history(241)
    official.attrs['source'] = 'SiamChart (SET index only)'
    with patch('src.screening.optimized_batch_processor.fetch_siamchart_index', return_value=official) as fetch:
        assert obj.fetch_spy_data()
        fetch.assert_called_once_with()
        assert len(obj.spy_data) == 241
    assert analyze_spy_trend(obj.spy_data, obj.spy_price)['slope_50'] is not None
    assert 'SiamChart' in analyze_spy_trend(obj.spy_data, obj.spy_price)['source']


def test_valid_yahoo_history_does_not_call_set():
    obj = processor(history(227))
    with patch('src.screening.optimized_batch_processor.fetch_siamchart_index') as fetch:
        assert obj.fetch_spy_data()
        fetch.assert_not_called()


def test_both_sources_unavailable_keep_signals_disabled():
    obj = processor(history(1))
    with patch('src.screening.optimized_batch_processor.fetch_siamchart_index', side_effect=ValueError('Unavailable')):
        assert obj.fetch_spy_data()
        assert len(obj.spy_data) == 1
        analysis = analyze_spy_trend(obj.spy_data, obj.spy_price)
        rec = should_generate_signals(analysis, calculate_market_breadth([]))
        assert not rec['should_generate_buys']
        assert not rec['should_generate_sells']


def test_report_handles_insufficient_benchmark(tmp_path):
    frame = history(1)
    analysis = analyze_spy_trend(frame, frame.Close.iloc[-1])
    breadth = calculate_market_breadth([])
    assert 'N/A' in format_benchmark_summary(analysis, breadth)
    results = dict(total_processed=0, total_analyzed=0, processing_time_seconds=0,
                   actual_tps=0, error_rate=0)
    path = save_report(results, [], [], analysis, breadth, output_dir=tmp_path)
    assert path.exists()
    assert 'N/A' in (tmp_path / 'latest_optimized_scan.txt').read_text()
