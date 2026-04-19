from core.api.websocket_feed import MultiSymbolWebSocketFeed

def test_callback(symbol, data):
    print(f"[{symbol}] Nowa świeca: O={data['open']} C={data['close']} V={data['volume']}")

ws = MultiSymbolWebSocketFeed(["BTCUSDT", "ETHUSDT"], test_callback)
ws.start()
input("Naciśnij Enter, aby zakończyć...\n")
ws.stop()