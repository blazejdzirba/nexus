import pandas as pd
import duckdb
import os
import sys

# --- NAPRAWA IMPORTÓW ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config
from core.engine.strategy import NexusStrategyEngine
from core.engine.trade_manager import VirtualWallet


def backtest_symbol(symbol, data_dir, start_date, end_date, strategy_params, wallet_params):
    """Pełny backtest dla jednego symbolu."""
    conn = duckdb.connect()

    # Elastyczne wyszukiwanie pliku
    possible_file = None
    for tf in ['5m', '1m', '15m', '']:
        candidate = os.path.join(
            data_dir,
            f"{symbol}_{tf}_latest.parquet" if tf else f"{symbol}.parquet"
        )
        if os.path.exists(candidate):
            possible_file = candidate
            break

    if possible_file is None:
        possible_file = os.path.join(data_dir, f"{symbol}_5m_latest.parquet")

    if not os.path.exists(possible_file):
        print(f"[!] Brak danych dla {symbol}")
        return None

    try:
        query = f"""
            SELECT timestamp, open, high, low, close, volume 
            FROM read_parquet('{possible_file}')
            WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY timestamp
        """
        df = conn.execute(query).fetchdf()
    except Exception as e:
        print(f"[ERROR] Błąd odczytu {symbol}: {e}")
        return None
    finally:
        conn.close()

    if df.empty or len(df) < 200:          # podniosłem minimalną ilość
        print(f"[!] {symbol} – za mało danych ({len(df)} świec)")
        return None

    # Konwersja typów
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=['close'], inplace=True)
    df['symbol'] = symbol

    # === STRATEGIA ===
    engine = NexusStrategyEngine(params=strategy_params)
    df = engine.calculate_signals(df)

    # === WALLET ===
    wallet = VirtualWallet(
        initial_balance=wallet_params.get('initial_balance', 10000),
        risk_per_trade=wallet_params.get('risk_per_trade', 2.0),
        max_positions=wallet_params.get('max_positions', 5),
        leverage=wallet_params.get('leverage', 10),
        commission=wallet_params.get('commission', 0.001),
        slippage=wallet_params.get('slippage', 0.0005),
        live_mode=False
    )

    # === GŁÓWNA PĘTLA ===
    equity = []
    TP_PERCENT = 2.5      # dopasowane do Twojego indicatora (Krypto)
    SL_PERCENT = 10.0

    for _, row in df.iterrows():
        current_time = row['timestamp']
        current_close = row['close']

        wallet.check_tp_sl(current_price=current_close, timestamp=current_time)

        if len(wallet.active_positions) < wallet.max_positions:
            if row.get('setup_bullish', False):
                tp = current_close * (1 + TP_PERCENT / 100)
                sl = current_close * (1 - SL_PERCENT / 100)
                wallet.open_position(symbol=symbol, entry_price=current_close,
                                     tp=tp, sl=sl, direction=1, timestamp=current_time)

            elif row.get('setup_bearish', False):
                tp = current_close * (1 - TP_PERCENT / 100)
                sl = current_close * (1 + SL_PERCENT / 100)
                wallet.open_position(symbol=symbol, entry_price=current_close,
                                     tp=tp, sl=sl, direction=-1, timestamp=current_time)

        equity.append({
            'timestamp': current_time,
            'balance': round(wallet.balance, 2)
        })

    return {
        'trades': wallet.history,
        'equity': equity,
        'signals': df
    }


def run_multi_backtest(symbols, data_dir, start_date, end_date, strategy_params, wallet_params):
    """Uruchamia backtesty dla wielu symboli."""
    all_trades = []
    all_equity = []
    all_signals = []

    for sym in symbols:
        print(f"Backtesting {sym}...")
        res = backtest_symbol(sym, data_dir, start_date, end_date, strategy_params, wallet_params)

        if res:
            all_trades.extend(res['trades'])
            all_equity.extend(res['equity'])
            all_signals.append(res['signals'])          # zbieramy wszystkie

    if not all_equity:
        print("[!] Backtest nie wygenerował żadnych wyników equity.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    trades_df = pd.DataFrame(all_trades)
    equity_df = pd.DataFrame(all_equity)
    signals_df = pd.concat(all_signals, ignore_index=True)

    if 'timestamp' in equity_df.columns:
        equity_df = equity_df.sort_values('timestamp').reset_index(drop=True)

    # === ZAPIS DO BAZY (poprawiona wersja) ===
    if not signals_df.empty:
        db_path = os.path.join(os.path.dirname(data_dir), "signals.duckdb")
        conn = duckdb.connect(db_path)
        
        # Poprawione tworzenie tabeli
        conn.execute("DROP TABLE IF EXISTS signals")
        conn.register("temp_signals", signals_df)
        conn.execute("CREATE TABLE signals AS SELECT * FROM temp_signals")
        conn.unregister("temp_signals")
        conn.close()
        
        print(f"[DB] Zapisano {len(signals_df):,} wierszy do tabeli 'signals'")

    print(f"Zakończono. Transakcji: {len(trades_df)}")
    return trades_df, equity_df, signals_df


if __name__ == "__main__":
    print("🚀 Inicjalizacja testowego Backtestera...")

    test_symbols = ["BTCUSDT", "ETHUSDT"]

    if not hasattr(Config, 'DATA_DIR'):
        Config.DATA_DIR = str(BASE_DIR / "data" / "raw_parquet")
        Config.LOGS_DIR = str(BASE_DIR / "logs")

    data_directory = Config.DATA_DIR
    print(f"🔍 Folder danych: {data_directory}")

    wallet_params = {
        'initial_balance': 10000,
        'risk_per_trade': 2.0,
        'leverage': 10,
        'commission': 0.001,
        'slippage': 0.0005
    }

    strategy_params = {'ai_threshold': 55}      # lekko obniżyłem, żeby było więcej sygnałów

    start = "2024-01-01"      # polecam dłuższy okres do testów
    end = "2025-04-01"

    trades, equity, signals = run_multi_backtest(
        symbols=test_symbols,
        data_dir=data_directory,
        start_date=start,
        end_date=end,
        strategy_params=strategy_params,
        wallet_params=wallet_params
    )

    if not trades.empty:
        print("\n--- WYNIKI ---")
        print(trades[['symbol', 'entry_price', 'exit_price', 'pnl_percent', 'exit_reason']].to_string())