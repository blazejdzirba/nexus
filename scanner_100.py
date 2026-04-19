import time
import logging
import pandas as pd
from core.api.data_feed import BybitDataFeed
from core.engine.strategy import NexusStrategyEngine
from core.engine.trade_manager import VirtualWallet
from graph_engine import NexusOrchestrator
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("NEXUS-SCANNER")

def run_scanner():
    feed = BybitDataFeed()
    engine = NexusStrategyEngine()
    wallet = VirtualWallet()
    orchestrator = NexusOrchestrator()

    # Pobierz top 100 tickerów raz na cykl
    while True:
        try:
            logger.info("--- SKANOWANIE RYNKU (TOP 100) ---")
            tickers = feed.session.get_tickers(category="linear")['result']['list']
            top_100 = sorted(tickers, key=lambda x: float(x['turnover24h']), reverse=True)[:100]
            symbols = [t['symbol'] for t in top_100]
            current_prices = {t['symbol']: float(t['lastPrice']) for t in top_100}
            wallet.update_and_check(current_prices)

            # Wczytaj dane dla wszystkich symboli za jednym razem (unikamy wielokrotnego zapisu)
            data_dict = {}
            for sym in symbols:
                df = feed.fetch_historical_klines(sym, interval=Config.TIMEFRAME, limit=100)  # 100 świec
                if df is not None and not df.empty:
                    data_dict[sym] = df

            for sym, df in data_dict.items():
                df_res = engine.calculate_signals(df)
                last_row = df_res.iloc[-1]

                # Szybkie sito – wysoki score AI lub klasyczny nexus_score
                if last_row['ai_confidence'] >= 80 or last_row['nexus_score'] >= 0.80:
                    logger.info(f"[*] AI analizuje {sym} (score: {last_row['ai_confidence']:.1f})")
                    state = {
                        "symbol": sym,
                        "signal_score": float(last_row['nexus_score']),
                        "market_context": f"P:{last_row['close']}, AI:{last_row['ai_confidence']:.1f}",
                        "historical_matches": "",
                        "ai_decision": "",
                        "adjusted_sl": 0.0
                    }
                    final_state = orchestrator.graph.invoke(state)
                    if final_state.get("ai_decision") == "ZATWIERDZAM":
                        # Użyj preferowanego wejścia jeśli istnieje
                        entry = last_row['pref_entry_long'] if last_row['setup_bullish'] else last_row['pref_entry_short']
                        if pd.isna(entry):
                            entry = last_row['close']
                        wallet.open_trade(
                            symbol=sym,
                            price=entry,
                            direction=1 if last_row['setup_bullish'] else -1,
                            sl_percent=Config.SL_PERCENT,
                            tp1_percent=Config.TP1_PERCENT,
                            tp2_percent=Config.TP2_PERCENT,
                            tp3_percent=Config.TP3_PERCENT,
                            amount_usd=100
                        )
                        logger.info(f"[$$$] Otwarto pozycję na {sym} @ {entry:.2f}")

            logger.info(f"Koniec cyklu. Saldo: {wallet.balance:.2f} USDT")
            time.sleep(60)
        except Exception as e:
            logger.error(f"Błąd: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_scanner()