from pybit.unified_trading import HTTP
import pandas as pd
import numpy as np
import os

class BybitDataFeed:
    def __init__(self):
        self.session = HTTP(testnet=False)
        self.data_dir = "./data/raw_parquet"
        os.makedirs(self.data_dir, exist_ok=True)

    def fetch_historical_klines(self, symbol: str, interval: str = '1', limit: int = 1000):
        try:
            # Bybit akceptuje liczby jako interval dla minut, ale stringi dla 1h itp.
            response = self.session.get_kline(
                category="linear", symbol=symbol, interval=interval, limit=limit
            )

            if response['retCode'] == 0:
                df = pd.DataFrame(
                    response['result']['list'],
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
                )

                df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])

                df = df.sort_values('timestamp').reset_index(drop=True)
                df['symbol'] = symbol
                
                if 'turnover' in df.columns:
                    df = df.drop(columns=['turnover'])

                # --- IMPLEMENTACJA LOGIKI NEXUS-AI V6 ---
                df = self._apply_nexus_ai_logic(df)

                file_path = os.path.join(self.data_dir, f"{symbol}_{interval}m_latest.parquet")
                df.to_parquet(file_path, engine='fastparquet', index=False)
                return df
            return None
        except Exception as e:
            print(f"[ERROR] {e}")
            return None

    def _apply_nexus_ai_logic(self, df):
        """Odwzorowanie kluczowych wskaźników z pliku message.txt [cite: 1, 14]"""
        
        # 1. Normalizacja i Prosty Perceptron (AI Score) 
        def normalize(series, length=21):
            rolling_min = series.rolling(window=length).min()
            rolling_max = series.rolling(window=length).max()
            return 2 * ((series - rolling_min) / (rolling_max - rolling_min)) - 1

        # Obliczanie cech (Features) 
        # RSI 14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1+rs))
        
        # Momentum, Trend, Volume 
        feat_momentum = normalize(df['rsi'])
        ema9 = df['close'].ewm(span=9, adjust=False).mean()
        ema21 = df['close'].ewm(span=21, adjust=False).mean()
        feat_trend = normalize(ema9 - ema21)
        
        # Uproszczony AI Score (odpowiednik ai_confidence) [cite: 14, 15]
        df['ai_confidence'] = ((feat_momentum * 0.35) + (feat_trend * 0.40)) * 100

        # 2. Logika PVSRA (Volume Climax) 
        pvsra_length = 10
        df['v_sma'] = df['volume'].shift(1).rolling(window=pvsra_length).mean()
        df['v_max'] = df['volume'].shift(1).rolling(window=pvsra_length).max()
        
        df['pvsra_climax'] = (df['volume'] >= df['v_sma'] * 2.0) | (df['volume'] >= df['v_max'])
        
        # 3. Wykrywanie Setupów (Specjalista V5/V6) 
        # setupBullishRaw = pvsra_climax[1] i pvsra_climax[0] i świece wzrostowe 
        df['is_bull'] = df['close'] >= df['open']
        df['setup_bull'] = (df['pvsra_climax'].shift(1)) & (df['pvsra_climax']) & \
                           (df['is_bull'].shift(1)) & (df['is_bull']) & \
                           (df['ai_confidence'] >= 60.0) # Próg AI [cite: 1]

        return df

# Przykład użycia:
# feed = BybitDataFeed()
# data = feed.fetch_historical_klines("BTCUSDT", interval="15")
# print(data[data['setup_bull'] == True])