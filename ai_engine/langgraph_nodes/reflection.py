from typing import TypedDict

# 1. Definicja Stanu (State) dla LangGraph - ZOSTAWIONA JEDNA, CZYSTA DEFINICJA
class TradeState(TypedDict):
    symbol: str
    signal_score: float
    market_context: str
    historical_matches: str
    ai_decision: str
    adjusted_sl: float

# Klasa NexusAIAgent została USUNIĘTA - była to duplikacja logiki 
# obecnej w core/llm/llm_manager.py i core/llm/rag_manager.py
