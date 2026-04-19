import os
import json
import uuid
import datetime
import plotly.graph_objects as go
import pandas as pd
from config import Config

class PostMortemSystem:
    def __init__(self):
        # Korzystamy z scentralizowanego configu
        import chromadb
        self.chroma_client = chromadb.PersistentClient(path=Config.CHROMA_DIR)
        self.collection = self.chroma_client.get_or_create_collection(name="post_mortem_memory")

    def save_post_mortem(self, df_trade: pd.DataFrame, trade_details: dict):
        try:
            # 1. Walidacja danych (Data Integrity Check)
            if df_trade.empty or 'close' not in df_trade.columns:
                print("[ERROR] Pusty DataFrame w PostMortem. Przerywam.")
                return

            trade_id = str(uuid.uuid4())[:8]
            symbol = trade_details.get('symbol', 'UNKNOWN')
            pnl = float(trade_details.get('pnl', 0.0)) # Wymuszamy float

            # 2. Generowanie wykresu z zabezpieczeniem danych
            # Upewniamy się, że timestamp jest w formacie datetime dla Plotly
            df_plot = df_trade.copy()
            if not pd.api.types.is_datetime64_any_dtype(df_plot['timestamp']):
                df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp'])

            fig = go.Figure(data=[go.Candlestick(
                x=df_plot['timestamp'],
                open=df_plot['open'], high=df_plot['high'],
                low=df_plot['low'], close=df_plot['close'],
                name=symbol
            )])
            
            fig.update_layout(title=f"Trade {trade_id} | PnL: {pnl}%", template="plotly_dark")

            # 3. Zapis plików
            file_name = f"{symbol}_{trade_id}.html"
            chart_path = os.path.join(Config.CHARTS_DIR, file_name)
            fig.write_html(chart_path)

            # 4. ChromaDB Embedding
            # Tworzymy opis tekstowy dla RAG
            context_desc = f"Symbol: {symbol}, PnL: {pnl}%, RSI: {trade_details.get('rsi', 'N/A')}"
            
            self.collection.add(
                documents=[context_desc],
                metadatas=[{"trade_id": trade_id, "pnl": pnl, "symbol": symbol}],
                ids=[trade_id]
            )

            # 5. JSON Audit Trail
            log_path = os.path.join(Config.LOGS_DIR, f"{trade_id}.json")
            with open(log_path, 'w') as f:
                json.dump(trade_details, f, indent=4)

            print(f"[SUCCESS] Post-Mortem zapisany: {trade_id} (PnL: {pnl}%)")

        except Exception as e:
            print(f"[CRITICAL ERROR] PostMortem failed: {e}")