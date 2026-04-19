"""
Inicjalizacja bazy wektorowej ChromaDB dla RAG (Retrieval-Augmented Generation).
Uruchom raz, aby wypełnić pamięć przykładowymi danymi.
"""

import os
import sys
import chromadb
from chromadb.utils import embedding_functions
from config import Config

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def init_rag_database():
    """Tworzy i wypełnia bazę ChromaDB przykładowymi transakcjami."""
    
    # Inicjalizacja ChromaDB
    chroma_client = chromadb.PersistentClient(path=Config.CHROMA_DIR)
    ef = embedding_functions.DefaultEmbeddingFunction()
    
    # Usuń istniejącą kolekcję (jeśli chcesz zacząć od nowa)
    try:
        chroma_client.delete_collection("post_mortem_memory")
        print("[RAG] Usunięto starą kolekcję")
    except:
        pass
    
    # Utwórz nową kolekcję
    collection = chroma_client.create_collection(
        name="post_mortem_memory",
        embedding_function=ef
    )
    print(f"[RAG] Utworzono kolekcję: post_mortem_memory")
    
    # Przykładowe dane – każda krotka to (id, document, metadata)
    demo_trades = [
        (
            "trade_001",
            "BTCUSDT, LONG, RSI=25, Volume climax, FVG bullish, Trend up",
            {"symbol": "BTCUSDT", "pnl": 2.5, "direction": "LONG", "outcome": "WIN"}
        ),
        (
            "trade_002",
            "ETHUSDT, SHORT, RSI=75, Volume climax, FVG bearish, Trend down",
            {"symbol": "ETHUSDT", "pnl": 3.2, "direction": "SHORT", "outcome": "WIN"}
        ),
        (
            "trade_003",
            "SOLUSDT, LONG, RSI=30, High volume, No FVG, Consolidation",
            {"symbol": "SOLUSDT", "pnl": -1.8, "direction": "LONG", "outcome": "LOSS"}
        ),
        (
            "trade_004",
            "BTCUSDT, SHORT, RSI=80, Volume climax, FVG bearish, Trend down",
            {"symbol": "BTCUSDT", "pnl": 4.1, "direction": "SHORT", "outcome": "WIN"}
        ),
        (
            "trade_005",
            "ADAUSDT, LONG, RSI=28, Low volume, No climax, Range market",
            {"symbol": "ADAUSDT", "pnl": -2.3, "direction": "LONG", "outcome": "LOSS"}
        ),
        (
            "trade_006",
            "DOGEUSDT, SHORT, RSI=72, Climax volume, FVG bearish, Overextended",
            {"symbol": "DOGEUSDT", "pnl": 5.0, "direction": "SHORT", "outcome": "WIN"}
        ),
    ]
    
    # Dodaj dane do kolekcji
    ids = []
    documents = []
    metadatas = []
    
    for trade_id, doc, meta in demo_trades:
        ids.append(trade_id)
        documents.append(doc)
        metadatas.append(meta)
    
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    print(f"[RAG] Dodano {len(demo_trades)} przykładowych transakcji")
    
    # Test zapytania
    test_query = "BTCUSDT LONG climax volume"
    results = collection.query(query_texts=[test_query], n_results=2)
    print(f"\n[RAG] Test zapytania: '{test_query}'")
    print(f"Znaleziono: {results['documents'][0]}")
    
    return collection

if __name__ == "__main__":
    print("=== Inicjalizacja bazy RAG ===\n")
    init_rag_database()
    print("\n✅ Gotowe! Możesz teraz uruchomić dashboard.")