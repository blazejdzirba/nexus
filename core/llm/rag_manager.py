"""
Zarządzanie RAG (Retrieval-Augmented Generation) i cache decyzji LLM.
"""

import hashlib
import json
import os
import datetime
import logging
from typing import Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions
from config import Config

logger = logging.getLogger(__name__)

class RAGManager:
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or Config.LLM_CACHE_DIR
        self.chroma_client = chromadb.PersistentClient(path=Config.CHROMA_DIR)
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Pobierz lub utwórz kolekcję (poprawione except)
        try:
            self.collection = self.chroma_client.get_collection("post_mortem_memory")
        except Exception as e:
            logger.info("Tworzę nową kolekcję post_mortem_memory w ChromaDB")
            self.collection = self.chroma_client.create_collection(
                name="post_mortem_memory",
                embedding_function=self.ef
            )
    
    def retrieve_similar(self, query: str, n_results: int = 3) -> str:
        """Pobiera podobne transakcje z pamięci i zwraca jako string."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if not results['documents'] or not results['documents'][0]:
                return "Brak podobnych transakcji w pamięci."
            
            history = []
            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                pnl = meta.get('pnl', 0)
                outcome = "ZYSK" if pnl > 0 else "STRATA"
                history.append(f"- {doc} | Wynik: {outcome} ({pnl}%)")
            
            return "\n".join(history)
        except Exception as e:
            logger.error(f"[RAG] Błąd zapytania: {e}")
            return "Brak podobnych transakcji (błąd zapytania)."
    
    def add_trade_to_memory(self, trade_data: Dict[str, Any]):
        """Dodaje zakończoną transakcję do pamięci RAG."""
        try:
            trade_id = f"{trade_data['symbol']}_{trade_data['exit_time']}_{hashlib.md5(str(trade_data).encode()).hexdigest()[:8]}"
            document = f"{trade_data['symbol']}, {trade_data['direction']}, RSI={trade_data.get('rsi', 50)}, PnL={trade_data.get('pnl_percent', 0)}%"
            metadata = {
                "symbol": trade_data['symbol'],
                "pnl": trade_data.get('pnl_percent', 0),
                "direction": trade_data['direction'],
                "outcome": "WIN" if trade_data.get('pnl_percent', 0) > 0 else "LOSS",
                "exit_reason": trade_data.get('exit_reason', 'UNKNOWN')
            }
            
            self.collection.add(
                ids=[trade_id],
                documents=[document],
                metadatas=[metadata]
            )
            logger.info(f"[RAG] Dodano transakcję {trade_id} do pamięci")
        except Exception as e:
            logger.error(f"[RAG] Błąd dodawania do pamięci: {e}")


class LLMCache:
    """Cache decyzji LLM – oszczędza tokeny i czas."""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or Config.LLM_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_file = os.path.join(self.cache_dir, "decisions_cache.json")
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
    
    def _make_key(self, symbol: str, signal_score: float, market_context: str, historical_matches: str) -> str:
        """Tworzy hash z parametrów zapytania."""
        content = f"{symbol}_{signal_score}_{market_context}_{historical_matches}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, symbol: str, signal_score: float, market_context: str, historical_matches: str) -> Optional[str]:
        """Zwraca cached response lub None."""
        key = self._make_key(symbol, signal_score, market_context, historical_matches)
        if key in self.cache:
            cached = self.cache[key]
            try:
                cache_time = datetime.datetime.fromisoformat(cached['timestamp'])
                if datetime.datetime.now() - cache_time < datetime.timedelta(days=1):
                    return cached['response']
                else:
                    del self.cache[key]
                    self._save_cache()
            except (ValueError, TypeError):
                del self.cache[key]
                self._save_cache()
        return None
    
    def set(self, symbol: str, signal_score: float, market_context: str, historical_matches: str, response: str):
        """Zapisuje odpowiedź w cache."""
        key = self._make_key(symbol, signal_score, market_context, historical_matches)
        self.cache[key] = {
            'response': response,
            'timestamp': datetime.datetime.now().isoformat()
        }
        self._save_cache()
    
    def clear(self):
        """Czyści cały cache."""
        self.cache = {}
        self._save_cache()
        logger.info("Cache LLM wyczyszczony")