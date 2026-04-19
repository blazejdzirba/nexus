# config.py — PEŁNA WERSJA
import os

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # Katalogi danych
    DATA_DIR       = os.path.join(BASE_DIR, "data", "raw_parquet")
    CHROMA_DIR     = os.path.join(BASE_DIR, "data", "chroma_db")
    LOGS_DIR       = os.path.join(BASE_DIR, "logs", "trades")
    RESULTS_DIR    = os.path.join(BASE_DIR, "results")
    PRESETS_DIR    = os.path.join(BASE_DIR, "config", "presets")

    # BRAKUJĄCE — dodane teraz
    LLM_CACHE_DIR  = os.path.join(BASE_DIR, "cache", "llm")
    CHARTS_DIR     = os.path.join(BASE_DIR, "dashboard", "static", "charts")

    # Model AI
    MODEL_NAME = "phi3"

    # Symbole domyślne
    SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    # Parametry skanera
    TIMEFRAME   = "1"      # 1-minutowe świece Bybit
    SL_PERCENT  = 2.0      # Stop Loss %
    TP1_PERCENT = 2.0      # Take Profit 1 %
    TP2_PERCENT = 4.0      # Take Profit 2 %
    TP3_PERCENT = 6.0      # Take Profit 3 %

    @classmethod
    def initialize_env(cls):
        dirs = [
            cls.DATA_DIR, cls.CHROMA_DIR, cls.LOGS_DIR,
            cls.RESULTS_DIR, cls.PRESETS_DIR,
            cls.LLM_CACHE_DIR, cls.CHARTS_DIR,
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        core_init = os.path.join(cls.BASE_DIR, "core", "__init__.py")
        if not os.path.exists(core_init):
            os.makedirs(os.path.dirname(core_init), exist_ok=True)
            open(core_init, "w").close()

Config.initialize_env()