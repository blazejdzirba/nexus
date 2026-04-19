import time
import pandas as pd
import os
from pybit.unified_trading import WebSocket
from config import Config

# Ścieżka do danych
SAVE_DIR = "data/raw_parquet"
os.makedirs(SAVE_DIR, exist_ok=True)

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT"] # Dodaj swoje 100 symboli

def handle_kline(message):
    try:
        data = message['data'][0]
        symbol = message['topic'].split('.')[-1]
        
        if data['confirm']: # Zapisujemy tylko zamknięte świece
            filename = f"{SAVE_DIR}/{symbol}_1m_latest.parquet"
            
            new_row = {
                "timestamp": int(data['start']),
                "open": float(data['open']),
                "high": float(data['high']),
                "low": float(data['low']),
                "close": float(data['close']),
                "volume": float(data['volume'])
            }
            
            df_new = pd.DataFrame([new_row])
            
            if os.path.exists(filename):
                df_old = pd.read_parquet(filename)
                df_final = pd.concat([df_old, df_new]).drop_duplicates('timestamp').tail(2000)
            else:
                df_final = df_new
                
            df_final.to_parquet(filename)
            print(f"[WS] Zaktualizowano {symbol}")
    except Exception as e:
        print(f"[ERROR] WS: {e}")

ws = WebSocket(testnet=False, channel_type="linear")

for s in symbols:
    ws.kline_stream(interval=1, symbol=s, callback=handle_kline)

print("=== LIVE STREAMER URUCHOMIONY – NASŁUCHIWANIE WEBSOCKET ===")
while True:
    time.sleep(1)