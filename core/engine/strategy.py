import pandas as pd
import numpy as np
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)

class NexusStrategyEngine:
    """
    Zaawansowany silnik strategii NEXUS z obsługą Multi-Timeframe (MTF).
    """
    def __init__(self, params=None):
        self.params = params or {}
        # POPRAWKA: Wagi rozdzielone logicznie, dodano 'trend'
        self.weights = self.params.get('weights', {
            'fvg': 0.2, 
            'pvsra': 0.15, 
            'rsi': 0.25, 
            'mfi': 0.1,
            'trend': 0.3  # <-- DODANO KLUCZ 'trend'
        })
        
        self.rsi_length = self.params.get('rsi_length', 14)
        self.ema_htf_len = self.params.get('ema_htf_len', 200)
        self.pvsra_climax_mult = self.params.get('pvsra_climax_mult', 2.0)
        self.ai_threshold = self.params.get('ai_threshold', 60)

    def add_htf_indicators(self, df_5m):
        df_5m = df_5m.copy()
        df_5m['timestamp'] = pd.to_datetime(df_5m['timestamp'])
        
        df_1h = df_5m.resample('1H', on='timestamp').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).dropna()
        
        df_1h['ema200_1h'] = ta.ema(df_1h['close'], length=self.ema_htf_len)
        df_5m = df_5m.merge(df_1h[['ema200_1h']], left_on='timestamp', right_index=True, how='left')
        df_5m['ema200_1h'] = df_5m['ema200_1h'].ffill()
        return df_5m

    def _add_pvsra(self, df):
        vol_ma = df['volume'].rolling(10).mean()
        df['pvsra_climax'] = np.where(df['volume'] > vol_ma * self.pvsra_climax_mult, 1, 0)
        return df

    def _add_ai_perceptron(self, df):
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_length).fillna(50)
        feat_rsi = (df['rsi'] - 50) / 50
        feat_trend = np.where(df['close'] > df['ema200_1h'], 1, -1)
        
        # POPRAWKA: Używamy poprawnego klucza 'trend' zamiast 'fvg'
        df['ai_confidence'] = (
            (feat_rsi * self.weights['rsi']) + 
            (feat_trend * self.weights['trend'])
        ) * 100
        return df

    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.add_htf_indicators(df)
        df = self._add_pvsra(df)
        df = self._add_ai_perceptron(df)
        
        df['setup_bullish'] = (df['pvsra_climax'] == 1) & (df['close'] > df['ema200_1h']) & (df['ai_confidence'] > self.ai_threshold)
        df['setup_bearish'] = (df['pvsra_climax'] == 1) & (df['close'] < df['ema200_1h']) & (df['ai_confidence'] < -self.ai_threshold)
        
        df['nexus_score'] = (df['ai_confidence'] + 100) / 200
        return df