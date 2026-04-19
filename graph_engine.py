import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from ai_engine.langgraph_nodes.reflection import NexusAIAgent, TradeState

# Konfiguracja Logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NEXUS_GRAPH")

class NexusOrchestrator:
    def __init__(self):
        self.agent = NexusAIAgent()
        self.builder = StateGraph(TradeState)
        
        # Definicja węzłów
        self.builder.add_node("retrieve_memory", self.agent.retrieve_memory_node)
        self.builder.add_node("analyze_signal", self.agent.decision_node)
        self.builder.add_node("self_critique", self.self_critique_node)
        
        # Definicja krawędzi
        self.builder.set_entry_point("retrieve_memory")
        self.builder.add_edge("retrieve_memory", "analyze_signal")
        self.builder.add_edge("analyze_signal", "self_critique")
        
        # Logika warunkowa: Jeśli krytyka przejdzie, kończymy. Jeśli nie, wracamy do analizy.
        self.builder.add_conditional_edges(
            "self_critique",
            self.should_continue,
            {
                "valid": END,
                "retry": "analyze_signal"
            }
        )
        self.graph = self.builder.compile()

    def self_critique_node(self, state: TradeState) -> TradeState:
        logger.info(f"Krytyka decyzji dla {state['symbol']}...")
        if state["ai_decision"] == "ZATWIERDZAM" and state["adjusted_sl"] > 2.0:
            logger.warning("KRYTYKA: Stop Loss zbyt szeroki (>2%). Wymuszam korektę.")
            state["ai_decision"] = "RETRY"
    # Dodatkowe: jeśli dźwignia > 10, odrzuć
        if state.get("leverage", 10) > 10:
            logger.warning("KRYTYKA: Dźwignia >10x niedozwolona.")
        state["ai_decision"] = "RETRY"

        return state

    def self_critique_node(self, state: TradeState) -> TradeState:
        """Weryfikacja decyzji pod kątem zarządzania ryzykiem."""
        logger.info(f"Krytyka decyzji dla {state['symbol']}...")
        
        # Prosta logika deterministyczna jako 'Safety Guard'
        if state["ai_decision"] == "ZATWIERDZAM" and state["adjusted_sl"] > 2.0:
            logger.warning("KRYTYKA: Stop Loss zbyt szeroki (>2%). Wymuszam korektę.")
            state["ai_decision"] = "RETRY"
        
        return state

    def should_continue(self, state: TradeState) -> Literal["valid", "retry"]:
        if state["ai_decision"] == "RETRY":
            return "retry"
        return "valid"

    def run(self, initial_state: TradeState):
        return self.graph.invoke(initial_state)