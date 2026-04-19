import time
import pandas as pd
import os
from pybit.unified_trading import HTTP
from config import Config

session = HTTP(testnet=False)
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"] # Twoja lista

def sync_data():
    for symbol in symbols:
        try:
            print(f"[REST] Pobieranie {symbol}...")
            resp = session.get_kline(category="linear", symbol=symbol, interval=1, limit=1000)
            
            # Konwersja na DF
            raw = resp['result']['list']
            df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].astype(float)
            df = df.sort_values('timestamp')

            path = f"data/raw_parquet/{symbol}_1m_latest.parquet"
            df.to_parquet(path)
            
            # KLUCZ: Oddech dla API (uwalnia od błędu 10006)
            time.sleep(0.25) 
            
        except Exception as e:
            print(f"Błąd przy {symbol}: {e}")
            time.sleep(2) # Dłuższa przerwa po błędzie

if __name__ == "__main__":
    sync_data()