"""
WebSocket Feed dla wielu symboli (1-minutowe klines)
"""

import threading
import json
from typing import List, Callable
from pybit.unified_trading import WebSocket

class MultiSymbolWebSocketFeed:
    def __init__(self, symbols: List[str], on_kline_callback: Callable[[str, dict], None]):
        self.symbols = symbols
        self.callback = on_kline_callback
        self.ws = None
        self.is_running = False
        self._thread = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_websocket, daemon=True)
        self._thread.start()

    def _run_websocket(self):
        self.ws = WebSocket(
            testnet=False,
            channel_type="linear"
        )
        # Subskrybuj każdy symbol
        for sym in self.symbols:
            self.ws.kline_stream(symbol=sym, interval=1, callback=self._handle_message)

    def _handle_message(self, message):
        """
        Obsługa wiadomości – może być dict lub list.
        """
        try:
            # Jeśli to lista – przetwórz każdy element
            if isinstance(message, list):
                for item in message:
                    self._process_single_message(item)
            else:
                self._process_single_message(message)
        except Exception as e:
            print(f"[WebSocket] Błąd ogólny: {e}")

    def _process_single_message(self, msg):
        """Przetwarza pojedynczą wiadomość."""
        try:
            # Sprawdź czy to słownik
            if not isinstance(msg, dict):
                return
            
            topic = msg.get("topic", "")
            if not topic or "kline" not in topic:
                return
            
            # Wyciągnij symbol
            symbol = topic.split(".")[-1]
            data = msg.get("data", {})
            if not data:
                return
            
            # Sprawdź czy świeca jest zamknięta
            if data.get("confirm", 0) == 0:
                return
            
            self.callback(symbol, data)
        except Exception as e:
            print(f"[WebSocket] Błąd przetwarzania wiadomości: {e}")

    def stop(self):
        self.is_running = False
        if self.ws:
            self.ws.exit()
        if self._thread:
            self._thread.join(timeout=2)