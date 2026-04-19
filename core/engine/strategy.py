import pandas as pd
import numpy as np
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)


class NexusStrategyEngine:
    def __init__(self, params=None):
        self.params = params or {}
        self.ai_threshold = self.params.get('ai_threshold', 60.0)
        self.use_strict_ai = self.params.get('use_strict_ai', True)
        self.lookback = self.params.get('lookback', 21)

    # ====================== NORMALIZACJA (zabezpieczona przed NaN) ======================
    def _f_normalize(self, src: pd.Series, length: int) -> pd.Series:
        """Dokładna kopia z Pine + ochrona przed NaN"""
        src = src.fillna(0).ffill()                     # <-- najważniejsze zabezpieczenie
        rolling_max = src.rolling(length, min_periods=1).max()
        rolling_min = src.rolling(length, min_periods=1).min()

        res = np.where(
            rolling_max == rolling_min,
            0,
            2 * ((src - rolling_min) / (rolling_max - rolling_min)) - 1
        )
        return pd.Series(res, index=src.index)

    # ====================== PVSRA na 1H ======================
    def _add_pvsra_1h(self, df_1h: pd.DataFrame) -> pd.DataFrame:
        pvsra_length = 10
        vol_ma = df_1h['volume'].rolling(pvsra_length).mean()
        vol_highest = df_1h['volume'].rolling(pvsra_length).max()

        df_1h['pvsra_climax'] = (
            (df_1h['volume'] >= vol_ma * 2.0) |
            (df_1h['volume'] >= vol_highest)
        ).astype(int)

        df_1h['is_bull'] = (df_1h['close'] >= df_1h['open']).astype(int)
        df_1h['is_bear'] = (df_1h['close'] < df_1h['open']).astype(int)
        return df_1h

    # ====================== AI PERCEPTRON ======================
    def _add_ai_perceptron(self, df: pd.DataFrame) -> pd.DataFrame:
        # Obliczamy wskaźniki z pandas_ta
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema9'] = ta.ema(df['close'], length=9)
        df['ema21'] = ta.ema(df['close'], length=21)
        df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)

        # Normalizacja
        feat_momentum = self._f_normalize(df['rsi'], self.lookback)
        feat_trend = self._f_normalize(df['ema9'] - df['ema21'], self.lookback)
        feat_volume = self._f_normalize(df['mfi'], self.lookback)

        ai_raw_score = (feat_momentum * 0.35) + (feat_trend * 0.40) + (feat_volume * 0.25)
        df['ai_confidence'] = ai_raw_score * 100

        return df

    # ====================== GŁÓWNA METODA ======================
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

        # Resample do 1H (PVSRA + AI liczymy na wyższym TF)
        df_1h = df.resample('1h').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum'
        }).dropna()

        df_1h = self._add_pvsra_1h(df_1h)
        df_1h = self._add_ai_perceptron(df_1h)

        # Przenosimy sygnały z 1H na oryginalny timeframe (5m/1m)
        df = df.merge(
            df_1h[['pvsra_climax', 'is_bull', 'is_bear', 'ai_confidence']],
            left_index=True, right_index=True, how='left'
        )
        df = df.ffill()                     # wypełniamy NaN-y z 1H

        # Setup dokładnie jak w Pine Script V6
        setup_bull_raw = (
            (df['pvsra_climax'].shift(1) == 1) &
            (df['pvsra_climax'] == 1) &
            (df['is_bull'].shift(1) == 1) &
            (df['is_bull'] == 1)
        )
        setup_bear_raw = (
            (df['pvsra_climax'].shift(1) == 1) &
            (df['pvsra_climax'] == 1) &
            (df['is_bear'].shift(1) == 1) &
            (df['is_bear'] == 1)
        )

        ai_valid_bull = (df['ai_confidence'] >= self.ai_threshold) if self.use_strict_ai else True
        ai_valid_bear = (df['ai_confidence'] <= -self.ai_threshold) if self.use_strict_ai else True

        df['setup_bullish'] = setup_bull_raw & ai_valid_bull
        df['setup_bearish'] = setup_bear_raw & ai_valid_bear

        df['trade_signal'] = np.where(df['setup_bullish'], 1, np.where(df['setup_bearish'], -1, 0))
        df['nexus_score'] = (df['ai_confidence'] + 100) / 200

        df.reset_index(inplace=True)
        return df