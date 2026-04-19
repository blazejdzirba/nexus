"""
NEXUS-AI — Inspekcja bazy danych historycznych.
Pokazuje: jakie coiny, jakie zakresy dat, ile danych, co można backtestować.
Uruchom: python inspect_data.py
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config


# ── Kolory w terminalu ──────────────────────────────────────────────
G  = "\033[92m"   # zielony
Y  = "\033[93m"   # żółty
R  = "\033[91m"   # czerwony
B  = "\033[94m"   # niebieski
W  = "\033[97m"   # biały
DIM = "\033[2m"   # przyciemniony
RST = "\033[0m"   # reset


def fmt_rows(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.0f}K"
    return str(n)


def backtest_verdict(days: float) -> str:
    """Co można backtestować przy danej liczbie dni danych."""
    if days >= 365:  return f"{G}✅ Wszystko (rok+){RST}"
    if days >= 90:   return f"{G}✅ Strategie swing/trend{RST}"
    if days >= 30:   return f"{Y}⚠️  Krótkoterminowe strategie{RST}"
    if days >= 7:    return f"{Y}⚠️  Tylko testy techniczne{RST}"
    return               f"{R}❌ Za mało (< 7 dni){RST}"


def scan_parquet_files(data_dir: str) -> list[dict]:
    """Skanuje folder i zwraca info o każdym pliku parquet."""
    results = []
    parquet_files = sorted(Path(data_dir).glob("**/*.parquet"))

    if not parquet_files:
        return results

    for fpath in parquet_files:
        size_mb = fpath.stat().st_size / 1_048_576
        try:
            df = pd.read_parquet(fpath, columns=['timestamp'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.dropna()

            if df.empty:
                continue

            ts_sorted = df['timestamp'].sort_values()
            start     = ts_sorted.iloc[0]
            end       = ts_sorted.iloc[-1]
            rows      = len(df)
            days      = (end - start).total_seconds() / 86400
            gap_days  = (datetime.now() - end).days

            # Wykryj timeframe z nazwy pliku
            name = fpath.stem  # np. BTCUSDT_1m_latest
            if '_1m_' in name:  tf = '1m'
            elif '_5m_' in name: tf = '5m'
            elif '_15m_' in name: tf = '15m'
            elif '_1h_' in name: tf = '1h'
            else:                tf = '?'

            # Wykryj symbol
            symbol = name.split('_')[0]

            # Sprawdź ciągłość (czy nie ma dużych dziur)
            if rows > 1 and tf == '1m':
                expected_rows = days * 24 * 60
                completeness  = min(rows / max(expected_rows, 1) * 100, 100)
            else:
                completeness = None

            results.append({
                'symbol':       symbol,
                'timeframe':    tf,
                'start':        start,
                'end':          end,
                'rows':         rows,
                'days':         days,
                'size_mb':      size_mb,
                'gap_days':     gap_days,
                'completeness': completeness,
                'path':         str(fpath),
            })

        except Exception as e:
            results.append({
                'symbol':    fpath.stem,
                'error':     str(e),
                'path':      str(fpath),
            })

    return results


def print_report(records: list[dict]):
    total_mb   = sum(r.get('size_mb', 0)  for r in records if 'error' not in r)
    total_rows = sum(r.get('rows', 0)     for r in records if 'error' not in r)
    ok_records = [r for r in records if 'error' not in r]
    err_records= [r for r in records if 'error'  in r]

    print(f"\n{W}{'═'*72}{RST}")
    print(f"{W}  NEXUS-AI — RAPORT BAZY DANYCH HISTORYCZNYCH{RST}")
    print(f"{W}{'═'*72}{RST}")
    print(f"  Folder : {B}{Config.DATA_DIR}{RST}")
    print(f"  Pliki  : {len(ok_records)} OK  |  {len(err_records)} błędów")
    print(f"  Łącznie: {fmt_rows(total_rows)} świec  |  {total_mb:.1f} MB na dysku")
    print(f"{'─'*72}")

    if not ok_records:
        print(f"\n{R}  Brak danych. Uruchom: python download_historical.py{RST}\n")
        return

    # Grupuj po timeframe
    by_tf = {}
    for r in ok_records:
        by_tf.setdefault(r['timeframe'], []).append(r)

    for tf, recs in sorted(by_tf.items()):
        print(f"\n{B}  Timeframe: {tf}  ({len(recs)} symboli){RST}")
        print(f"  {'Symbol':<16} {'Od':>11} {'Do':>11} {'Dni':>6} {'Świece':>8} {'MB':>6} {'Kompletność':>12} {'Opóźnienie':>11}")
        print(f"  {'─'*16} {'─'*11} {'─'*11} {'─'*6} {'─'*8} {'─'*6} {'─'*12} {'─'*11}")

        # Sortuj po symbolach
        for r in sorted(recs, key=lambda x: x['symbol']):
            sym   = r['symbol']
            start = r['start'].strftime('%Y-%m-%d')
            end   = r['end'].strftime('%Y-%m-%d')
            days  = r['days']
            rows  = fmt_rows(r['rows'])
            mb    = f"{r['size_mb']:.1f}"
            gap   = r['gap_days']

            # Kompletność
            if r['completeness'] is not None:
                c = r['completeness']
                if c >= 95:   comp = f"{G}{c:5.1f}%{RST}"
                elif c >= 80: comp = f"{Y}{c:5.1f}%{RST}"
                else:         comp = f"{R}{c:5.1f}%{RST}"
            else:
                comp = f"{DIM}   n/d{RST}"

            # Opóźnienie danych
            if gap == 0:       gap_str = f"{G}dzisiaj{RST}"
            elif gap <= 1:     gap_str = f"{G}wczoraj{RST}"
            elif gap <= 7:     gap_str = f"{Y}{gap} dni temu{RST}"
            else:              gap_str = f"{R}{gap} dni temu{RST}"

            # Kolor dni
            if days >= 90:    days_col = f"{G}{days:5.0f}{RST}"
            elif days >= 30:  days_col = f"{Y}{days:5.0f}{RST}"
            else:             days_col = f"{R}{days:5.0f}{RST}"

            print(f"  {sym:<16} {start:>11} {end:>11} {days_col:>6} {rows:>8} {mb:>6} {comp:>12}   {gap_str}")

    # ── SEKCJA: co można backtestować ────────────────────────────────
    print(f"\n{'─'*72}")
    print(f"{W}  CO MOŻNA BACKTESTOWAĆ (na obecnych danych):{RST}\n")

    if ok_records:
        max_days   = max(r['days'] for r in ok_records)
        min_days   = min(r['days'] for r in ok_records)
        common_end = min(r['end']  for r in ok_records)

        # Symbole z wystarczającą ilością danych
        symbols_30d  = [r['symbol'] for r in ok_records if r['days'] >= 30]
        symbols_90d  = [r['symbol'] for r in ok_records if r['days'] >= 90]
        symbols_365d = [r['symbol'] for r in ok_records if r['days'] >= 365]

        print(f"  Najdłuższy zakres  : {G}{max_days:.0f} dni{RST}")
        print(f"  Najkrótszy zakres  : {''.join([G if min_days>=30 else Y if min_days>=7 else R])}{min_days:.0f} dni{RST}")
        print(f"  Wspólna data końca : {common_end.strftime('%Y-%m-%d')} (najstarsza data końcowa)")

        print(f"\n  Symbole z 30+ dni  ({len(symbols_30d)})  : {', '.join(symbols_30d[:10])}{'...' if len(symbols_30d)>10 else ''}")
        print(f"  Symbole z 90+ dni  ({len(symbols_90d)}) : {', '.join(symbols_90d[:10])}{'...' if len(symbols_90d)>10 else ''}")
        print(f"  Symbole z 365+ dni ({len(symbols_365d)}) : {', '.join(symbols_365d[:10]) if symbols_365d else 'brak'}")

        # Bezpieczne zakresy dat dla backtestu
        print(f"\n  {W}Bezpieczne zakresy dla run_multi_backtest():{RST}")

        ranges = [
            ("7 dni",   timedelta(days=7)),
            ("30 dni",  timedelta(days=30)),
            ("90 dni",  timedelta(days=90)),
            ("180 dni", timedelta(days=180)),
            ("365 dni", timedelta(days=365)),
        ]
        for label, delta in ranges:
            cutoff = common_end - delta
            eligible = [r['symbol'] for r in ok_records if r['start'] <= cutoff and r['end'] >= common_end - timedelta(days=1)]
            if eligible:
                print(f"  {label:<10}: {len(eligible):>3} symboli  │  start='{cutoff.strftime('%Y-%m-%d')}', end='{common_end.strftime('%Y-%m-%d')}'")

    # ── Błędy ────────────────────────────────────────────────────────
    if err_records:
        print(f"\n{R}  Pliki z błędami:{RST}")
        for r in err_records:
            print(f"  {R}✗{RST} {r['path']}")
            print(f"    {DIM}{r['error']}{RST}")

    print(f"\n{'═'*72}\n")


def interactive_query(records: list[dict]):
    """Mini-REPL do odpytywania danych."""
    ok = [r for r in records if 'error' not in r]
    if not ok:
        return

    print(f"{W}  TRYB INTERAKTYWNY — wpisz symbol lub 'q' aby wyjść{RST}")
    print(f"  Dostępne symbole: {', '.join(sorted(set(r['symbol'] for r in ok)))}\n")

    while True:
        try:
            inp = input(f"  {B}symbol>{RST} ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            break

        if inp in ('Q', 'EXIT', ''):
            break

        matches = [r for r in ok if r['symbol'] == inp]
        if not matches:
            print(f"  {R}Nie znaleziono: {inp}{RST}")
            continue

        for r in matches:
            print(f"\n  {W}{r['symbol']} ({r['timeframe']}){RST}")
            print(f"  Start      : {r['start'].strftime('%Y-%m-%d %H:%M')}")
            print(f"  Koniec     : {r['end'].strftime('%Y-%m-%d %H:%M')}")
            print(f"  Dni danych : {r['days']:.1f}")
            print(f"  Świece     : {r['rows']:,}")
            print(f"  Rozmiar    : {r['size_mb']:.2f} MB")
            print(f"  Ścieżka    : {DIM}{r['path']}{RST}")
            print(f"  Backtest   : {backtest_verdict(r['days'])}")

            if r.get('completeness'):
                c = r['completeness']
                bar_len = 30
                filled = int(bar_len * c / 100)
                bar = '█' * filled + '░' * (bar_len - filled)
                color = G if c >= 95 else Y if c >= 80 else R
                print(f"  Kompletność: {color}[{bar}] {c:.1f}%{RST}")
        print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Inspekcja danych NEXUS-AI")
    parser.add_argument('--query', '-q', action='store_true',
                        help='Tryb interaktywny — szczegóły dla konkretnego symbolu')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Eksportuj wyniki jako JSON')
    args = parser.parse_args()

    print(f"\n{DIM}Skanowanie {Config.DATA_DIR} ...{RST}")
    records = scan_parquet_files(Config.DATA_DIR)
    print_report(records)

    if args.json:
        import json
        out = []
        for r in records:
            row = {k: str(v) if isinstance(v, (pd.Timestamp, datetime)) else v
                   for k, v in r.items() if k != 'path'}
            out.append(row)
        fname = "data_report.json"
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"Zapisano: {fname}")

    if args.query:
        interactive_query(records)
