"""
NEXUS-AI Specjalista V6
Strategia oparta na PVSRA (climax volume), AI Perceptron, FVG, poziomach HTF i dynamicznym wyborze wejścia.
Zgodna z logiką wskaźnika TradingView o tej samej nazwie.
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)


class NexusStrategyEngineV6:
    """
    Silnik strategii NEXUS-AI V6.
    Parametry:
    - ai_threshold: próg pewności AI (0-100), domyślnie 60
    - use_strict_ai: czy wymagać potwierdzenia AI (True/False)
    - lookback: okno normalizacji cech AI (domyślnie 21)
    - market_type: 'Krypto' lub 'Tradycyjna' (wpływa na TP/SL)
    - tp_sl_params: słownik z procentami dla TP1, TP2, TP3, SL (nadpisuje domyślne)
    - ema_retest_len: długość EMA dla retestu (domyślnie 200)
    - fvg_box_length: długość prostokąta FVG (w świecach) – tylko informacyjnie
    """
    def __init__(self, params=None):
        self.params = params or {}
        self.ai_threshold = self.params.get('ai_threshold', 60.0)
        self.use_strict_ai = self.params.get('use_strict_ai', True)
        self.lookback = self.params.get('lookback', 21)
        self.market_type = self.params.get('market_type', 'Krypto')
        self.ema_retest_len = self.params.get('ema_retest_len', 200)
        self.fvg_box_length = self.params.get('fvg_box_length', 5)  # tylko do adnotacji
        self.tp_sl_params = self.params.get('tp_sl_params', {})

        # Domyślne wartości TP/SL (w procentach)
        if self.market_type == 'Krypto':
            self.tp1 = self.tp_sl_params.get('tp1', 2.5)
            self.tp2 = self.tp_sl_params.get('tp2', 5.0)
            self.tp3 = self.tp_sl_params.get('tp3', 7.5)
            self.sl = self.tp_sl_params.get('sl', 10.0)
        else:  # Tradycyjna
            self.tp1 = self.tp_sl_params.get('tp1', 1.0)
            self.tp2 = self.tp_sl_params.get('tp2', 2.0)
            # TP3 dla rynku tradycyjnego = TP2 + (TP2 - TP1)
            self.tp3 = self.tp_sl_params.get('tp3', self.tp2 + (self.tp2 - self.tp1))
            self.sl = self.tp_sl_params.get('sl', self.tp2 * 2.0)

        # Długości dla HTS (wstęgi)
        self.hts_fast_len = self.params.get('hts_fast_len', 21)
        self.hts_slow_len = self.params.get('hts_slow_len', 55)

        # Długość RSI dla ostrzeżeń
        self.rsi_length = self.params.get('rsi_length', 14)
        self.rsi_ob = self.params.get('rsi_ob', 80)
        self.rsi_os = self.params.get('rsi_os', 25)

    # =========================== POMOCNICZE ===========================
    def _normalize(self, src: pd.Series, length: int) -> pd.Series:
        """Normalizacja do zakresu [-1, 1] z zabezpieczeniem przed dzieleniem przez zero."""
        src = src.fillna(0)
        rolling_min = src.rolling(window=length, min_periods=1).min()
        rolling_max = src.rolling(window=length, min_periods=1).max()
        diff = rolling_max - rolling_min
        # Unikamy dzielenia przez zero
        norm = 2 * ((src - rolling_min) / diff.replace(0, np.nan)) - 1
        return norm.fillna(0)

    # =========================== PVSRA (Climax / HighVol) ===========================
    def _add_pvsra(self, df: pd.DataFrame) -> pd.DataFrame:
        """Dodaje kolumny: pvsra_climax, pvsra_high_vol, is_bull, is_bear."""
        df = df.copy()
        length = 10
        vol_ma = df['volume'].rolling(length, min_periods=1).mean()
        vol_highest = df['volume'].rolling(length, min_periods=1).max()

        df['pvsra_climax'] = (df['volume'] >= vol_ma * 2.0) | (df['volume'] >= vol_highest)
        df['pvsra_high_vol'] = (df['volume'] >= vol_ma * 1.5) & (~df['pvsra_climax'])

        df['is_bull'] = (df['close'] >= df['open']).astype(int)
        df['is_bear'] = (df['close'] < df['open']).astype(int)
        return df

    # =========================== AI PERCEPTRON ===========================
    def _add_ai_perceptron(self, df: pd.DataFrame) -> pd.DataFrame:
        """Oblicza ai_confidence (od -100 do 100). Wagi: momentum 0.35, trend 0.40, volume 0.25."""
        df = df.copy()
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema9'] = ta.ema(df['close'], length=9)
        df['ema21'] = ta.ema(df['close'], length=21)
        df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)

        feat_momentum = self._normalize(df['rsi'], self.lookback)
        feat_trend = self._normalize(df['ema9'] - df['ema21'], self.lookback)
        feat_volume = self._normalize(df['mfi'], self.lookback)

        # Wagi zgodne z Pine V6 (momentum 0.35, trend 0.40, volume 0.25)
        ai_raw_score = (feat_momentum * 0.35) + (feat_trend * 0.40) + (feat_volume * 0.25)
        df['ai_confidence'] = np.clip(ai_raw_score * 100, -100, 100)
        return df

    # =========================== HTS (wstęgi) ===========================
    def _add_hts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Dodaje kolumny hts_fast, hts_slow, hts_up (szybka > wolna)."""
        df = df.copy()
        df['hts_fast'] = ta.ema(df['close'], length=self.hts_fast_len)
        df['hts_slow'] = ta.ema(df['close'], length=self.hts_slow_len)
        df['hts_up'] = df['hts_fast'] > df['hts_slow']
        return df

    # =========================== POZIOMY HTF (Previous Day/Week) ===========================
    def _add_htf_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Oblicza dla każdej świecy:
        - pdh, pdl (poprzedni dzień high/low)
        - pwh, pwl (poprzedni tydzień high/low)
        Zakładamy, że dane mają kolumnę 'timestamp' jako datetime i są posortowane rosnąco.
        """
        df = df.copy()
        df['date'] = df['timestamp'].dt.date
        df['week'] = df['timestamp'].dt.isocalendar().week

        # Daily levels
        daily_high = df.groupby('date')['high'].max()
        daily_low = df.groupby('date')['low'].min()
        df['daily_high'] = df['date'].map(daily_high)
        df['daily_low'] = df['date'].map(daily_low)
        # Previous day high/low (shift)
        df['pdh'] = df['daily_high'].shift(1)
        df['pdl'] = df['daily_low'].shift(1)

        # Weekly levels
        weekly_high = df.groupby('week')['high'].max()
        weekly_low = df.groupby('week')['low'].min()
        df['weekly_high'] = df['week'].map(weekly_high)
        df['weekly_low'] = df['week'].map(weekly_low)
        # Previous week high/low (shift)
        df['pwh'] = df['weekly_high'].shift(1)
        df['pwl'] = df['weekly_low'].shift(1)

        # EMA retest level
        df['ema_retest'] = ta.ema(df['close'], length=self.ema_retest_len)

        # Usuwamy kolumny pomocnicze
        df.drop(['date', 'week', 'daily_high', 'daily_low', 'weekly_high', 'weekly_low'], axis=1, inplace=True)
        return df

    # =========================== FVG (Fair Value Gaps) ===========================
    def _add_fvg(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identyfikuje FVG bullish i bearish.
        Bullish FVG: low[0] > high[2]  (przerwa między świecą 2 i 0)
        Bearish FVG: high[0] < low[2]
        Dodaje kolumny: bullish_fvg, bearish_fvg, fvg_top, fvg_bottom, fvg_mid.
        """
        df = df.copy()
        # Przesunięcia
        high_shift2 = df['high'].shift(2)
        low_shift2 = df['low'].shift(2)

        df['bullish_fvg'] = (df['low'] > high_shift2) & (~high_shift2.isna())
        df['bearish_fvg'] = (df['high'] < low_shift2) & (~low_shift2.isna())

        # Wartości dla FVG
        df['fvg_top'] = np.where(df['bullish_fvg'], df['low'], np.where(df['bearish_fvg'], low_shift2, np.nan))
        df['fvg_bottom'] = np.where(df['bullish_fvg'], high_shift2, np.where(df['bearish_fvg'], df['high'], np.nan))
        df['fvg_mid'] = (df['fvg_top'] + df['fvg_bottom']) / 2

        return df

    # =========================== GENEROWANIE SETUPÓW ===========================
    def _generate_setups(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generuje sygnały na podstawie PVSRA (2x climax) + potwierdzenie AI.
        Dodaje kolumny: setup_bullish, setup_bearish, trade_signal.
        """
        df = df.copy()
        # Warunki raw (bez AI)
        climax = df['pvsra_climax'].astype(bool)
        bull_raw = climax.shift(1) & climax & (df['is_bull'].shift(1) == 1) & (df['is_bull'] == 1)
        bear_raw = climax.shift(1) & climax & (df['is_bear'].shift(1) == 1) & (df['is_bear'] == 1)

        # Warunki AI
        ai_bull_valid = (~self.use_strict_ai) | (df['ai_confidence'] >= self.ai_threshold)
        ai_bear_valid = (~self.use_strict_ai) | (df['ai_confidence'] <= -self.ai_threshold)

        df['setup_bullish'] = bull_raw & ai_bull_valid
        df['setup_bearish'] = bear_raw & ai_bear_valid

        df['trade_signal'] = 0
        df.loc[df['setup_bullish'], 'trade_signal'] = 1
        df.loc[df['setup_bearish'], 'trade_signal'] = -1

        return df

    # =========================== PREFEROWANE WEJŚCIE (RETEST) ===========================
    def _preferred_entry(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Dla każdego sygnału wybiera optymalny poziom wejścia spośród:
        - FVG 50% (mid)
        - EMA retest
        - PDH / PWH (dla long) lub PDL / PWL (dla short)
        Dodaje kolumny: pref_entry_price, pref_entry_level.
        """
        df = df.copy()
        df['pref_entry_price'] = np.nan
        df['pref_entry_level'] = ''

        # Dla każdego wiersza z sygnałem (ale tylko gdy setup wystąpił)
        long_signals = df[df['setup_bullish']].index
        short_signals = df[df['setup_bearish']].index

        for idx in long_signals:
            # Obliczamy odległości do potencjalnych poziomów (tylko jeśli są poniżej close i powyżej low[1])
            row = df.loc[idx]
            close = row['close']
            low_prev = df['low'].shift(1).loc[idx]

            candidates = {}
            # FVG mid (jeśli istnieje bullish FVG na tej samej świecy? W Pine bierze FVG z bieżącej świecy)
            if row['bullish_fvg'] and not pd.isna(row['fvg_mid']) and row['fvg_mid'] < close and row['fvg_mid'] > low_prev:
                candidates[row['fvg_mid']] = 'FVG 50%'
            # EMA retest
            ema_val = row['ema_retest']
            if not pd.isna(ema_val) and ema_val < close and ema_val > low_prev:
                candidates[ema_val] = f'EMA {self.ema_retest_len}'
            # PDH
            pdh = row['pdh']
            if not pd.isna(pdh) and pdh < close and pdh > low_prev:
                candidates[pdh] = 'PDH'
            # PWH
            pwh = row['pwh']
            if not pd.isna(pwh) and pwh < close and pwh > low_prev:
                candidates[pwh] = 'PWH'

            if candidates:
                # Wybieramy poziom najbliższy do close (minimalna odległość)
                best = min(candidates.keys(), key=lambda x: abs(close - x))
                df.loc[idx, 'pref_entry_price'] = best
                df.loc[idx, 'pref_entry_level'] = candidates[best]
            else:
                # Domyślnie 50% zakresu (high + low[1])/2
                default = (row['high'] + low_prev) / 2
                df.loc[idx, 'pref_entry_price'] = default
                df.loc[idx, 'pref_entry_level'] = '50% Move'

        for idx in short_signals:
            row = df.loc[idx]
            close = row['close']
            high_prev = df['high'].shift(1).loc[idx]

            candidates = {}
            if row['bearish_fvg'] and not pd.isna(row['fvg_mid']) and row['fvg_mid'] > close and row['fvg_mid'] < high_prev:
                candidates[row['fvg_mid']] = 'FVG 50%'
            ema_val = row['ema_retest']
            if not pd.isna(ema_val) and ema_val > close and ema_val < high_prev:
                candidates[ema_val] = f'EMA {self.ema_retest_len}'
            pdl = row['pdl']
            if not pd.isna(pdl) and pdl > close and pdl < high_prev:
                candidates[pdl] = 'PDL'
            pwl = row['pwl']
            if not pd.isna(pwl) and pwl > close and pwl < high_prev:
                candidates[pwl] = 'PWL'

            if candidates:
                best = min(candidates.keys(), key=lambda x: abs(close - x))
                df.loc[idx, 'pref_entry_price'] = best
                df.loc[idx, 'pref_entry_level'] = candidates[best]
            else:
                default = (row['low'] + high_prev) / 2
                df.loc[idx, 'pref_entry_price'] = default
                df.loc[idx, 'pref_entry_level'] = '50% Move'

        return df

    # =========================== TP/SL ===========================
    def _add_tp_sl(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Dla każdego sygnału dodaje poziomy TP1, TP2, TP3, SL (ceny).
        Uwzględnia kierunek.
        """
        df = df.copy()
        for col in ['tp1', 'tp2', 'tp3', 'sl']:
            df[col] = np.nan

        long_mask = df['setup_bullish']
        short_mask = df['setup_bearish']

        # LONG
        if long_mask.any():
            entry = df.loc[long_mask, 'close']
            df.loc[long_mask, 'tp1'] = entry * (1 + self.tp1 / 100)
            df.loc[long_mask, 'tp2'] = entry * (1 + self.tp2 / 100)
            df.loc[long_mask, 'tp3'] = entry * (1 + self.tp3 / 100)
            df.loc[long_mask, 'sl']  = entry * (1 - self.sl / 100)

        # SHORT
        if short_mask.any():
            entry = df.loc[short_mask, 'close']
            df.loc[short_mask, 'tp1'] = entry * (1 - self.tp1 / 100)
            df.loc[short_mask, 'tp2'] = entry * (1 - self.tp2 / 100)
            df.loc[short_mask, 'tp3'] = entry * (1 - self.tp3 / 100)
            df.loc[short_mask, 'sl']  = entry * (1 + self.sl / 100)

        return df

    # =========================== OSTRZEŻENIA (RSI, HTS) ===========================
    def _add_warnings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Dodaje ostrzeżenia: warning_rsi, warning_hts."""
        df = df.copy()
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_length)
        df['warning_rsi'] = np.where(
            (df['setup_bullish'] & (df['rsi'] > self.rsi_ob)) |
            (df['setup_bearish'] & (df['rsi'] < self.rsi_os)),
            True, False
        )
        df['warning_hts'] = np.where(
            (df['setup_bullish'] & (~df['hts_up'])) |
            (df['setup_bearish'] & (df['hts_up'])),
            True, False
        )
        return df

    # =========================== METODA GŁÓWNA ===========================
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Wejście: DataFrame z kolumnami: timestamp, open, high, low, close, volume.
        Wyjście: DataFrame z dodanymi kolumnami sygnałów, poziomami, ostrzeżeniami.
        """
        # Walidacja
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Brak wymaganej kolumny: {col}")

        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.sort_values('timestamp', inplace=True)

        # Kolejność obliczeń
        df = self._add_pvsra(df)
        df = self._add_ai_perceptron(df)
        df = self._add_hts(df)
        df = self._add_htf_levels(df)
        df = self._add_fvg(df)
        df = self._generate_setups(df)
        df = self._preferred_entry(df)
        df = self._add_tp_sl(df)
        df = self._add_warnings(df)

        # Dodatkowe kolumny ułatwiające analizę
        df['nexus_score'] = (df['ai_confidence'] + 100) / 200  # 0-1
        return df


# Przykład użycia:
if __name__ == '__main__':
    # Symulacja danych (w rzeczywistości wczytaj z pliku lub API)
    dates = pd.date_range('2024-01-01', periods=500, freq='1H')
    np.random.seed(42)
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.randn(500).cumsum() + 100,
        'high': np.random.randn(500).cumsum() + 101,
        'low': np.random.randn(500).cumsum() + 99,
        'close': np.random.randn(500).cumsum() + 100,
        'volume': np.random.randint(100, 10000, 500)
    })
    # Poprawiamy high/low
    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)

    engine = NexusStrategyEngineV6(params={
        'ai_threshold': 60,
        'use_strict_ai': True,
        'market_type': 'Krypto',
        'tp_sl_params': {'tp1': 2.5, 'tp2': 5.0, 'tp3': 7.5, 'sl': 10.0}
    })
    signals = engine.calculate_signals(df)
    print(signals[['timestamp', 'close', 'ai_confidence', 'setup_bullish', 'setup_bearish',
                   'pref_entry_price', 'pref_entry_level', 'tp1', 'sl', 'warning_rsi']].head(20))