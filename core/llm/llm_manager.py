"""
Zarządzanie LLM (phi3) z RAG, cache i logowaniem promptów.
"""

import json
import os
import datetime
import logging
from typing import Dict, Any, List
from langchain_ollama import OllamaLLM
from core.llm.rag_manager import RAGManager, LLMCache
from config import Config

logger = logging.getLogger(__name__)

class LLMManager:
    def __init__(self, model_name: str = "phi3", log_dir: str = None):
        self.llm = OllamaLLM(model=model_name)
        self.log_dir = log_dir or os.path.join(Config.LOGS_DIR, "llm")
        os.makedirs(self.log_dir, exist_ok=True)
        self.rag = RAGManager()
        self.cache = LLMCache()
        self.system_prompt = None

    def set_system_prompt(self, system_prompt: str):
        self.system_prompt = system_prompt

    def ask_with_rag(self, symbol: str, signal_score: float, market_context: str, use_cache: bool = True) -> Dict[str, Any]:
        query = f"{symbol} {market_context}"
        historical_matches = self.rag.retrieve_similar(query, n_results=3)
        
        if use_cache:
            cached = self.cache.get(symbol, signal_score, market_context, historical_matches)
            if cached:
                return self._parse_response(cached, from_cache=True)
        
        user_prompt = self._build_user_prompt(symbol, signal_score, market_context, historical_matches)
        full_prompt = self._build_full_prompt(user_prompt)
        
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "symbol": symbol,
            "signal_score": signal_score,
            "market_context": market_context,
            "historical_matches": historical_matches,
            "user_prompt": user_prompt,
            "full_prompt": full_prompt,
            "response": None,
            "error": None,
            "from_cache": False
        }
        
        try:
            response = self.llm.invoke(full_prompt)
            log_entry["response"] = response.strip()
            self._save_log(log_entry)
            
            self.cache.set(symbol, signal_score, market_context, historical_matches, response.strip())
            return self._parse_response(response.strip(), from_cache=False)
        except Exception as e:
            log_entry["error"] = str(e)
            self._save_log(log_entry)
            logger.error(f"Błąd LLM dla {symbol}: {e}")
            return {"decision": "ODRZUCAM", "sl": 0.0, "error": str(e)}
    
    def _build_full_prompt(self, user_prompt: str) -> str:
        if self.system_prompt:
            return f"{self.system_prompt}\n\n{user_prompt}"
        return user_prompt
    
    def _build_user_prompt(self, symbol: str, signal_score: float, market_context: str, historical_matches: str) -> str:
        return f"""Symbol: {symbol}
Sygnał techniczny (score): {signal_score}
Kontekst rynkowy: {market_context}
Podobne transakcje z przeszłości (RAG):
{historical_matches}

Odpowiedz w formacie:
DECYZJA: ZATWIERDZAM lub ODRZUCAM
SL: liczba (procent stop loss, np. 1.5)"""
    
    def _parse_response(self, response: str, from_cache: bool = False) -> Dict[str, Any]:
        """Parsuje odpowiedź LLM na słownik z POPRAWNĄ obsługą błędów."""
        decision = "ODRZUCAM"
        sl = 0.0
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.upper().startswith("DECYZJA:"):
                val = line.replace("DECYZJA:", "").strip().upper()
                decision = "ZATWIERDZAM" if "ZATWIERDZAM" in val else "ODRZUCAM"
            elif line.upper().startswith("SL:"):
                try:
                    sl = float(line.replace("SL:", "").strip().replace(",", "."))
                except (ValueError, AttributeError):  # <-- FIX: zamiast gołego except:
                    sl = 0.0
        
        return {
            "decision": decision,
            "sl": sl,
            "raw_response": response,
            "from_cache": from_cache
        }
    
    def _save_log(self, log_entry: dict):
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"llm_log_{date_str}.json")
        logs = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except json.JSONDecodeError:
                logs = []
        logs.append(log_entry)
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    
    def get_logs(self, date: str = None, limit: int = 100) -> List[dict]:
        if date is None:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"llm_log_{date}.json")
        if not os.path.exists(log_file):
            return []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            return logs[-limit:]
        except json.JSONDecodeError:
            return []