import os
import time
import threading
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP

# ─────────────────────────────────────────────
# RATE LIMITER — globalny semafor dla wszystkich wątków
# Bybit public API: 10 req/s per IP
# Zostawiamy margines → max 5 req/s
# ─────────────────────────────────────────────
_RATE_LOCK = threading.Semaphore(1)   # 1 request na raz
_MIN_INTERVAL = 0.25                  # 250ms między requestami = 4 req/s (bezpieczne)
_last_request_time = 0.0
_time_lock = threading.Lock()


def _rate_limited_request(session, **kwargs):
    """Każdy request przechodzi przez ten wrapper — gwarantuje min. 250ms przerwy."""
    global _last_request_time
    with _time_lock:
        now = time.time()
        wait = _MIN_INTERVAL - (now - _last_request_time)
        if wait > 0:
            time.sleep(wait)
        _last_request_time = time.time()

    # Retry loop z exponential backoff
    for attempt in range(5):
        try:
            resp = session.get_kline(**kwargs)
            if resp['retCode'] == 0:
                return resp
            elif resp['retCode'] == 10006:  # rate limit
                backoff = 2 ** attempt
                print(f"[RATE LIMIT] Czekam {backoff}s (próba {attempt+1}/5)...")
                time.sleep(backoff)
            else:
                print(f"[API ERROR] retCode={resp['retCode']} msg={resp.get('retMsg')}")
                return None
        except Exception as e:
            print(f"[EXCEPTION] {e} — próba {attempt+1}/5")
            time.sleep(2 ** attempt)
    return None


def fetch_klines_range(session, symbol, interval, start_ms, end_ms):
    """Pobiera klines w zadanym przedziale (max 1000 świec na request)."""
    all_data = []
    page = 0

    while start_ms < end_ms:
        page += 1
        resp = _rate_limited_request(
            session,
            category="linear",
            symbol=symbol,
            interval=interval,
            start=start_ms,
            end=end_ms,
            limit=1000
        )

        if resp is None:
            print(f"[SKIP] {symbol} — brak odpowiedzi po retries")
            break

        data = resp['result']['list']
        if not data:
            break

        all_data.extend(data)

        # Bybit zwraca dane od najnowszych → bierzemy najstarszy timestamp
        oldest_ts = int(data[-1][0])
        if oldest_ts <= start_ms:
            break
        start_ms = oldest_ts + 1

        # Progress co 10 stron
        if page % 10 == 0:
            fetched_days = (end_ms - start_ms) / (1000 * 60 * 60 * 24)
            print(f"[{symbol}] Strona {page}, zostało ~{fetched_days:.1f} dni...")

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(
        all_data,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
    )
    df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col])
    df = df.drop(columns=['turnover'], errors='ignore')
    df['symbol'] = symbol
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df


def download_symbol(symbol, start_date, end_date, interval='1', out_dir='data/raw_parquet'):
    """Pobiera i zapisuje dane dla jednego symbolu."""
    session = HTTP(testnet=False)
    start_ms = int(start_date.timestamp() * 1000)
    end_ms   = int(end_date.timestamp() * 1000)

    print(f"[START] {symbol} | {start_date.date()} → {end_date.date()}")

    df = fetch_klines_range(session, symbol, interval, start_ms, end_ms)

    if df.empty:
        print(f"[EMPTY] {symbol} — brak danych")
        return

    # Zapis flat (prosty, kompatybilny z dashboardem)
    os.makedirs(out_dir, exist_ok=True)
    flat_path = os.path.join(out_dir, f"{symbol}_{interval}m_latest.parquet")
    df.to_parquet(flat_path, engine='pyarrow', index=False)

    print(f"[OK] {symbol} → {len(df):,} świec → {flat_path}")


def download_all(symbols, start_date, end_date, interval='1',
                 out_dir='data/raw_parquet', max_workers=2):
    """
    Wielowątkowe pobieranie z kontrolą rate limit.
    max_workers=2 → bezpieczne dla Bybit public API.
    NIE zwiększaj powyżej 3 bez kluczy API premium.
    """
    total = len(symbols)
    print(f"\n{'='*50}")
    print(f"NEXUS Downloader | {total} symboli | workers={max_workers}")
    print(f"Szacowany czas: ~{total * 0.5:.0f}–{total * 2:.0f} minut")
    print(f"{'='*50}\n")

    success, failed = [], []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                download_symbol, sym, start_date, end_date, interval, out_dir
            ): sym for sym in symbols
        }
        for i, future in enumerate(as_completed(futures), 1):
            sym = futures[future]
            try:
                future.result()
                success.append(sym)
            except Exception as e:
                print(f"[FAIL] {sym}: {e}")
                failed.append(sym)
            print(f"Progress: {i}/{total} ({i/total*100:.0f}%)")

    print(f"\n{'='*50}")
    print(f"GOTOWE: {len(success)} sukces, {len(failed)} błędów")
    if failed:
        print(f"Błędy: {', '.join(failed)}")
    print(f"{'='*50}\n")


# ─────────────────────────────────────────────
# KONFIGURACJA POBIERANIA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    session = HTTP(testnet=False)

    # Pobierz listę symboli
    print("Pobieranie listy symboli z Bybit...")
    tickers = session.get_tickers(category="linear")['result']['list']
    top_symbols = sorted(
        tickers,
        key=lambda x: float(x.get('turnover24h', 0)),
        reverse=True
    )[:100]
    symbols = [t['symbol'] for t in top_symbols]
    print(f"Znaleziono {len(symbols)} symboli")

    # Zakres dat — ostatnie 30 dni (bezpieczny start)
    # Zmień days=30 na więcej gdy działa stabilnie
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=30)

    download_all(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        interval='1',           # 1-minutowe świece
        out_dir='data/raw_parquet',
        max_workers=2           # ← NIE zwiększaj bez premium API key
    )