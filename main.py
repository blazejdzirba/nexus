import sys
import os
import time
import logging

# Ustawienie ścieżek
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Importy NEXUS
from core.api.data_feed import BybitDataFeed
from core.engine.strategy import NexusStrategyEngine
from graph_engine import NexusOrchestrator
from dashboard.visualizer import PostMortemSystem

# Konfiguracja Logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("NEXUS-MAIN")

# Konfiguracja Handlu
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
INTERVAL = "1"

def run_nexus():
    logger.info("--- URUCHAMIANIE SYSTEMU NEXUS-AI (PROD MODE) ---")
    
    # Inicjalizacja komponentów
    try:
        orchestrator = NexusOrchestrator()
        feed = BybitDataFeed()
        engine = NexusStrategyEngine()
        pm = PostMortemSystem()
        logger.info("Wszystkie moduły zainicjalizowane pomyślnie.")
    except Exception as e:
        logger.error(f"Błąd inicjalizacji: {e}")
        return

    while True:
        try:
            for symbol in SYMBOLS:
                # 1. Pobieranie danych
                df = feed.fetch_historical_klines(symbol, interval=INTERVAL, limit=100)
                if df is None or df.empty:
                    continue

                # 2. Analiza Techniczna + Whale Detection
                df = engine.calculate_signals(df)
                df = engine.detect_whales(df)
                last_tick = df.iloc[-1]

                # 3. Logika Triggera (Signal lub Whale Activity)
                is_tech_signal = last_tick['trade_signal'] == 1
                is_whale_signal = last_tick.get('whale_buy', 0) == 1

                if is_tech_signal or is_whale_signal:
                    reason = "TECH" if is_tech_signal else "WHALE"
                    logger.info(f"[!] WYKRYTO SETUP ({reason}): {symbol} @ {last_tick['close']}")
                    
                    # 4. Egzekucja przez LangGraph (Refleksja + Self-Critique)
                    initial_state = {
                        "symbol": symbol,
                        "signal_score": float(last_tick['nexus_score']),
                        "market_context": f"Price: {last_tick['close']}, RSI: {last_tick['rsi']:.2f}, WhaleZ: {last_tick.get('vol_zscore',0):.2f}",
                        "historical_matches": "",
                        "ai_decision": "",
                        "adjusted_sl": 0.0
                    }
                    
                    # Graf podejmuje decyzję
                    final_state = orchestrator.run(initial_state)

                    if final_state["ai_decision"] == "ZATWIERDZAM":
                        logger.info(f"[$] DECYZJA AI: WEJŚCIE | SL: {final_state['adjusted_sl']}%")
                        
                        # 5. Zapis wizualny i pamięć
                        pm.save_post_mortem(df.tail(30), {
                            "symbol": symbol, 
                            "entry": last_tick['close'], 
                            "pnl": 0.0, 
                            "rsi": last_tick['rsi'],
                            "whale": int(is_whale_signal)
                        })
                    else:
                        logger.info(f"[-] DECYZJA AI: ODRZUCONO ({symbol})")
                
            # Odpoczynek pętli
            time.sleep(30)

        except Exception as e:
            logger.error(f"Błąd w pętli głównej: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_nexus()