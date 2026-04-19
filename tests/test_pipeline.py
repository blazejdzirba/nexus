import pandas as pd
import numpy as np
import datetime
from core.engine.strategy import NexusStrategyEngine
from ai_engine.langgraph_nodes.reflection import NexusAIAgent
from dashboard.visualizer import PostMortemSystem

def generate_synthetic_data():
    """Generuje syntetyczne świece 1m do testów, wymuszając FVG i PVSRA Climax."""
    print("[MOCK] Generowanie danych syntetycznych (HFT Mock)...")
    dates = pd.date_range(end=datetime.datetime.now(), periods=50, freq='1min')
    
    # Tworzymy bazowy DataFrame
    df = pd.DataFrame({
        'timestamp': dates,
        'symbol': 'BTCUSDT',
        'open': np.random.uniform(60000, 60100, 50),
        'high': np.random.uniform(60100, 60200, 50),
        'low': np.random.uniform(59900, 60000, 50),
        'close': np.random.uniform(60000, 60100, 50),
        'volume': np.random.uniform(10, 50, 50)
    })
    
    # Wstrzyknięcie formacji Bullish FVG i PVSRA na indeksie 48
    # FVG: Dzisiejsze Low (idx 48) > High sprzed 2 świec (idx 46)
    df.loc[46, 'high'] = 60000
    df.loc[48, 'low'] = 60050 
    df.loc[48, 'close'] = 60150
    df.loc[48, 'volume'] = 500 # PVSRA Climax (ogromny wolumen)
    
    return df

def run_test_pipeline():
    print("=== INICJALIZACJA NEXUS-AI PIPELINE ===")
    
    # 1. Inicjalizacja modułów
    strategy_engine = NexusStrategyEngine()
    ai_agent = NexusAIAgent()
    post_mortem = PostMortemSystem()
    
    # 2. Ingestia danych
    df = generate_synthetic_data()
    
    # 3. Silnik Strategii (Hardcoded Math)
    print("[SILNIK] Obliczanie sygnałów wektorowych...")
    df_signals = strategy_engine.calculate_signals(df)
    
    # Szukamy triggera
    triggers = df_signals[df_signals['trade_signal'] == 1]
    
    if triggers.empty:
        print("[SILNIK] Brak sygnałów. Zakończenie.")
        return

    latest_trigger = triggers.iloc[-1]
    print(f"[SILNIK] Znaleziono sygnał! Symbol: {latest_trigger['symbol']}, Score: {latest_trigger['nexus_score']:.2f}")
    
    # 4. Agent AI (Dual-Core Memory RAG)
    state = {
        "symbol": latest_trigger['symbol'],
        "signal_score": latest_trigger['nexus_score'],
        "market_context": f"Wykryto potężny wolumen i FVG. RSI wynosi {latest_trigger.get('rsi', 0):.2f}.",
        "historical_matches": "",
        "ai_decision": "",
        "adjusted_sl": 0.0
    }
    
    print("[AI AGENT] Odpytywanie pamięci wektorowej ChromaDB...")
    state = ai_agent.retrieve_memory_node(state)
    
    print("[AI AGENT] Analiza Llama 3 w toku (może zająć chwilę w zależności od GPU/CPU)...")
    state = ai_agent.decision_node(state)
    
    print(f"\n>>> DECYZJA AI: {state['ai_decision']} | Proponowany SL: {state['adjusted_sl']} <<<\n")
    
    # 5. Symulacja zamknięcia trade'a i Post-Mortem
    if state['ai_decision'] == 'ZATWIERDZAM':
        print("[SYSTEM] Egzekucja wirtualnego trade'a...")
        # Symulujemy wynik
        mock_pnl = 2.5 # Wirtualne +2.5% zysku
        
        trade_details = {
            "symbol": state['symbol'],
            "entry": latest_trigger['close'],
            "pnl": mock_pnl,
            "rsi": latest_trigger.get('rsi', 50)
        }
        
        print("[POST-MORTEM] Generowanie wizualizacji i zapisu do pamięci...")
        post_mortem.save_post_mortem(df, trade_details)
        print("=== TEST ZAKOŃCZONY SUKCESEM ===")

if __name__ == "__main__":
    run_test_pipeline()