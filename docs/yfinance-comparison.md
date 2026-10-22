# Yahoo download comparison (2026-10-22)

Reference implementations inspected:
- ghiatu/cookstock, src/cookStock.py: yf.download with explicit dates, auto_adjust=False, MultiIndex handling.
- ghiatu/set-thailand-screener-VCP, set100_screener.py: yf.download in chunks of 75, period=2y, ticker grouping, retry. Its RS ratings rank stock returns across the universe; the SET benchmark is not used in compute_rs_ratings.

Adoption: GitStorageFetcher.fetch_price_fresh now uses yf.download over two years. The reusable downloader supports chunks, retries, both MultiIndex layouts, valid numeric OHLC filtering, and truthful per-symbol row counts. Existing raw price semantics (auto_adjust=False) are preserved. The five-year stock drawdown calculation is unchanged.

Live comparison using the reference VCP call returned 484 non-null Close rows each for PTT.BK and ADVANC.BK, but only 1 for ^SET.BK. The cookstock explicit-date call likewise returned 1 SET row. A successful reference workflow therefore does not demonstrate 200 valid SET index observations.

The earlier guarded report behavior remains: insufficient SET history disables trading signals and reports N/A. This change adopts the reference download methods; it does NOT establish that Yahoo currently provides 200 SET index sessions. Do not pad dates, forward-fill 1 price into 200 sessions, or substitute an equity for the index.
