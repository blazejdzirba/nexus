import pandas as pd
import duckdb
import os
import sys
from datetime import datetime

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
    
    possible_file = os.path.join(data_dir, f"{symbol}_1m_latest.parquet")
    if not os.path.exists(possible_file):
        possible_file = os.path.join(data_dir, f"{symbol}.parquet")

    if not os.path.exists(possible_file):
        print(f"[!] Brak danych dla {symbol}")
        return None

    try:
        # Ograniczamy pobieranie tylko do potrzebnych kolumn dla szybkości
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

    if df.empty or len(df) < 100:
        return None

    # Konwersja typów
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=['close'], inplace=True)
    df['symbol'] = symbol

    # 1. Obliczanie sygnałów
    engine = NexusStrategyEngine(params=strategy_params)
    df = engine.calculate_signals(df)

    # 2. Inicjalizacja naprawionego Portfela
    wallet = VirtualWallet(
        initial_balance=wallet_params.get('initial_balance', 10000),
        risk_per_trade=wallet_params.get('risk_per_trade', 2.0),
        max_positions=wallet_params.get('max_positions', 5),
        leverage=wallet_params.get('leverage', 10),
        commission=wallet_params.get('commission', 0.001),
        slippage=wallet_params.get('slippage', 0.0005),
        live_mode=False # Backtest działa tylko w pamięci RAM
    )

    # 3. GŁÓWNA PĘTLA BACKTESTINGOWA (Zamiast stuba)
    equity = []
    
    # Parametry wejścia (dla uproszczenia sztywne TP/SL %, do rozbudowy)
    TP_PERCENT = 1.5
    SL_PERCENT = 0.8

    for index, row in df.iterrows():
        current_time = row['timestamp']
        current_close = row['close']
        
        # A. Sprawdź czy aktywne pozycje trafiły w TP/SL na tej świecy
        wallet.check_tp_sl(current_price=current_close, timestamp=current_time)

        # B. Szukaj nowych sygnałów wejścia (jeśli nie ma max pozycji)
        if len(wallet.active_positions) < wallet.max_positions:
            
            if row.get('setup_bullish', False):
                tp = current_close * (1 + TP_PERCENT / 100)
                sl = current_close * (1 - SL_PERCENT / 100)
                wallet.open_position(
                    symbol=symbol, 
                    entry_price=current_close, 
                    tp=tp, 
                    sl=sl, 
                    direction=1, 
                    timestamp=current_time
                )
            
            elif row.get('setup_bearish', False):
                tp = current_close * (1 - TP_PERCENT / 100)
                sl = current_close * (1 + SL_PERCENT / 100)
                wallet.open_position(
                    symbol=symbol, 
                    entry_price=current_close, 
                    tp=tp, 
                    sl=sl, 
                    direction=-1, 
                    timestamp=current_time
                )

        # C. Zapisz stan konta dla Equity Curve (co świecę)
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
    """Uruchamia backtesty wielowątkowo (sekwencyjnie dla stabilności RAM)."""
    all_trades = []
    all_equity = []
    all_signals = []

    for sym in symbols:
        print(f"Backtesting {sym}...")
        res = backtest_symbol(sym, data_dir, start_date, end_date, strategy_params, wallet_params)
        
        if res:
            all_trades.extend(res['trades'])
            all_equity.extend(res['equity'])
            # Signals łączymy tylko dla analizy, dla dużych danych lepiej to wyłączyć
            if len(all_signals) < 3: 
                all_signals.append(res['signals'])

    # Zabezpieczenie przed pustymi wynikami
    if not all_equity:
        print("[!] Backtest nie wygenerował żadnych wyników equity.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    trades_df = pd.DataFrame(all_trades)
    equity_df = pd.DataFrame(all_equity)
    signals_df = pd.concat(all_signals) if all_signals else pd.DataFrame()

    # Sortowanie equity
    if 'timestamp' in equity_df.columns:
        equity_df = equity_df.sort_values('timestamp').reset_index(drop=True)
        
    print(f"Zakończono. Transakcji: {len(trades_df)}")
    return trades_df, equity_df, signals_df


if __name__ == "__main__":
    print("🚀 Inicjalizacja testowego Backtestera...")
    
    test_symbols = ["BTCUSDT", "ETHUSDT"]
    
    # Wymusza config bez .env (dla testu CLI)
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
    
    strategy_params = {
        'ai_threshold': 60
    }
    
    start = "2024-10-01"
    end = "2024-10-10"
    
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