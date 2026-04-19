import duckdb
import pandas as pd

def save_backtest_results(trades_df, equity_df, signals_df, db_path="backtest_results.duckdb"):
    """Zapisuje wyniki oraz snapshoty cech dla każdego tradu."""
    conn = duckdb.connect(db_path)
    
    # Zapis głównych tabel
    conn.execute("CREATE OR REPLACE TABLE trades AS SELECT * FROM trades_df")
    conn.execute("CREATE OR REPLACE TABLE equity AS SELECT * FROM equity_df")
    
    if signals_df is not None and not signals_df.empty:
        conn.execute("CREATE OR REPLACE TABLE signals AS SELECT * FROM signals_df")
        
        # AUTOMATYCZNY TRADE JOURNALING: 
        # Łączymy tabelę trades z tabelą signals, aby wiedzieć jakie było RSI/Volume w momencie wejścia
        try:
            conn.execute("""
                CREATE OR REPLACE TABLE trade_journal AS
                SELECT 
                    t.*,
                    s.ai_confidence as entry_ai_conf,
                    s.rsi as entry_rsi,
                    s.pvsra_climax as entry_pvsra
                FROM trades t
                LEFT JOIN signals s ON t.symbol = s.symbol AND t.entry_time = s.timestamp
            """)
            print("[DB] Utworzono zaawansowany dziennik trade_journal")
        except Exception as e:
            print(f"[DB] Błąd journalingu: {e}")

    conn.close()