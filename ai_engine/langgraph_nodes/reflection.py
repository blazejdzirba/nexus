"""
NEXUS-AI — LangGraph node definitions.
Zawiera: TradeState (schema stanu) + NexusAIAgent (węzły grafu).
"""

from typing import TypedDict
from core.llm.llm_manager import LLMManager
from core.llm.rag_manager import RAGManager


class TradeState(TypedDict):
    """Schema stanu przepływającego przez graf LangGraph."""
    symbol:             str
    signal_score:       float
    market_context:     str
    historical_matches: str
    ai_decision:        str    # "ZATWIERDZAM" | "ODRZUCAM" | "RETRY"
    adjusted_sl:        float


class NexusAIAgent:
    """
    Agent AI obsługujący dwa węzły grafu:
      1. retrieve_memory_node — pobiera historyczne podobne transakcje z ChromaDB
      2. decision_node        — pyta LLM i parsuje decyzję
    """

    def __init__(self):
        self.llm = LLMManager()
        self.rag = RAGManager()

    def retrieve_memory_node(self, state: TradeState) -> TradeState:
        """
        Węzeł 1: odpytuje ChromaDB o podobne przeszłe transakcje.
        Wynik zapisuje w state['historical_matches'].
        """
        query = f"{state['symbol']} {state['market_context']}"
        state["historical_matches"] = self.rag.retrieve_similar(query, n_results=3)
        return state

    def decision_node(self, state: TradeState) -> TradeState:
        """
        Węzeł 2: wysyła kontekst do LLM i parsuje odpowiedź.
        Wynik zapisuje w state['ai_decision'] i state['adjusted_sl'].
        """
        result = self.llm.ask_with_rag(
            symbol=state["symbol"],
            signal_score=state["signal_score"],
            market_context=state["market_context"],
            use_cache=True,
        )
        state["ai_decision"] = result.get("decision", "ODRZUCAM")
        state["adjusted_sl"] = result.get("sl", 0.0)
        return state