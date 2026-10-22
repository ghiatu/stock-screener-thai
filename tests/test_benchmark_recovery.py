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


def test_truncated_response_recovers_with_explicit_dates():
    obj = processor(history(1))
    with patch('src.screening.optimized_batch_processor.yf.Ticker') as ticker:
        ticker.return_value.history.return_value = history(500)
        assert obj.fetch_spy_data()
        assert len(obj.spy_data) == 500
        assert 'start' in ticker.return_value.history.call_args.kwargs
        assert 'period' not in ticker.return_value.history.call_args.kwargs
    assert analyze_spy_trend(obj.spy_data, obj.spy_price)['slope_50'] is not None


def test_valid_history_does_not_retry():
    obj = processor(history(227))
    with patch('src.screening.optimized_batch_processor.yf.Ticker') as ticker:
        assert obj.fetch_spy_data()
        ticker.assert_not_called()


def test_retries_reject_short_and_nan_history():
    obj = processor(history(1))
    invalid = history(500)
    invalid['Close'] = np.nan
    with patch('src.screening.optimized_batch_processor.yf.Ticker') as ticker:
        ticker.return_value.history.side_effect = [history(1), invalid]
        assert obj.fetch_spy_data()
        assert ticker.return_value.history.call_count == 2
        assert len(obj.spy_data) == 1
        analysis = analyze_spy_trend(obj.spy_data, obj.spy_price)
        rec = should_generate_signals(analysis, calculate_market_breadth([]))
        assert not rec["should_generate_buys"]
        assert not rec["should_generate_sells"]


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
