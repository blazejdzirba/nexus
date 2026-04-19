"""
Prosty test – czy strategia w ogóle działa na danych REST.
"""

import pandas as pd
from core.api.data_feed import BybitDataFeed
from core.engine.strategy import NexusStrategyEngine

def main():
    print("=== TEST STRATEGII NA DANYCH REST ===\n")
    
    feed = BybitDataFeed()
    engine = NexusStrategyEngine()
    
    # Pobierz dane dla BTCUSDT
    print("Pobieranie danych dla BTCUSDT...")
    df = feed.fetch_historical_klines("BTCUSDT", interval="5", limit=100)
    
    if df is None or df.empty:
        print("❌ Brak danych!")
        return
    
    print(f"✅ Pobrano {len(df)} świec")
    
    # Oblicz sygnały
    print("Obliczanie sygnałów...")
    try:
        df = engine.calculate_signals(df)
        print("✅ Sygnały obliczone")
    except Exception as e:
        print(f"❌ Błąd calculate_signals: {e}")
        return
    
    # Sprawdź dostępne kolumny
    print(f"\n📊 Dostępne kolumny: {df.columns.tolist()}")
    
    # Sprawdź sygnały
    bullish_col = 'setup_bullish' if 'setup_bullish' in df.columns else None
    bearish_col = 'setup_bearish' if 'setup_bearish' in df.columns else None
    ai_col = 'ai_confidence' if 'ai_confidence' in df.columns else None
    
    if bullish_col and ai_col:
        signals = df[df[bullish_col] == True]
        print(f"\n📈 Sygnały bullish: {len(signals)}")
        if len(signals) > 0:
            print(signals[['timestamp', 'close', ai_col]].tail())
    else:
        print(f"\n⚠️ Brak kolumn: bullish={bullish_col}, ai={ai_col}")
    
    if bearish_col and ai_col:
        signals = df[df[bearish_col] == True]
        print(f"\n📉 Sygnały bearish: {len(signals)}")
        if len(signals) > 0:
            print(signals[['timestamp', 'close', ai_col]].tail())
    
    # Podsumowanie AI confidence
    if ai_col:
        print(f"\n🤖 AI Confidence: min={df[ai_col].min():.1f}, max={df[ai_col].max():.1f}, mean={df[ai_col].mean():.1f}")

if __name__ == "__main__":
    main()