import pandas as pd
import ccxt
import os
from config import Config

class DataSynchronizer:
    def __init__(self):
        self.bybit = ccxt.bybit()
        self.binance = ccxt.binance()

    def sync_symbol(self, symbol, timeframe='5m', days_back=365):
        """Pobiera dane z Binance (historia) i Bybit (aktualne), łącząc je w jeden plik."""
        path = os.path.join(Config.DATA_DIR, f"{symbol}_{timeframe}_latest.parquet")
        since = self.bybit.milliseconds() - (days_back * 24 * 60 * 60 * 1000)
        
        print(f"[*] Synchronizacja {symbol}...")
        
        try:
            # 1. Próba Bybit
            bybit_ohlcv = self.bybit.fetch_ohlcv(symbol, timeframe, since, limit=1000)
            df_bybit = pd.DataFrame(bybit_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 2. Uzupełnienie z Binance (jeśli Bybit nie ma pełnej historii)
            binance_ohlcv = self.binance.fetch_ohlcv(symbol, timeframe, since, limit=1000)
            df_binance = pd.DataFrame(binance_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Łączenie i usuwanie duplikatów
            df_combined = pd.concat([df_binance, df_bybit]).drop_duplicates(subset='timestamp').sort_values('timestamp')
            df_combined['timestamp'] = pd.to_datetime(df_combined['timestamp'], unit='ms')
            
            # Zapis do Parquet
            df_combined.to_parquet(path, index=False)
            print(f"[OK] Zapisano {len(df_combined)} świec w {path}")
            
        except Exception as e:
            print(f"[ERROR] Nie udało się zsynchronizować {symbol}: {e}")

if __name__ == "__main__":
    sync = DataSynchronizer()
    for sym in Config.SYMBOLS:
        sync.sync_symbol(sym, days_back=365)