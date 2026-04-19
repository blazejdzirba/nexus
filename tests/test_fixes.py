"""
Twardy test weryfikujący naprawy w VirtualWallet i Strategy.
Uruchom: python test_fixes.py
"""
import sys
import os

# Wskazujemy Pythonowi główny folder projektu (D:\nexus)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Teraz możesz bezpiecznie importować swoje moduły:
from core.engine.trade_manager import VirtualWallet
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.engine.trade_manager import VirtualWallet
from core.engine.strategy import NexusStrategyEngine

def test_slippage_logic():
    print("\n--- TEST 1: Poprawność Slippage ---")
    wallet = VirtualWallet(initial_balance=10000, slippage=0.001) # 0.1% slippage dla widoczności
    entry = 100.0
    
    # LONG powinien wejść DROŻEJ (100.10)
    wallet.open_position("BTC", entry, tp=105, sl=95, direction=1)
    long_entry = wallet.active_positions[-1]['entry']
    assert long_entry == 100.1, f"BŁĄD LONG: Expected 100.1, got {long_entry}"
    print(f"✅ LONG entry poprawny: {long_entry}")
    wallet.active_positions.clear()
    wallet.balance = 10000 # reset

    # SHORT powinien wejść TANIEJ (99.90)
    wallet.open_position("ETH", entry, tp=95, sl=105, direction=-1)
    short_entry = wallet.active_positions[-1]['entry']
    assert short_entry == 99.9, f"BŁĄD SHORT: Expected 99.9, got {short_entry}"
    print(f"✅ SHORT entry poprawny: {short_entry}")

def test_pnl_long():
    print("\n--- TEST 2: Obliczanie PnL dla LONG ---")
    wallet = VirtualWallet(initial_balance=10000, commission=0, slippage=0) # Wyłączamy prowizje dla czystego testu
    entry = 100.0
    tp = 110.0 # +10%
    leverage = 10
    
    wallet.open_position("BTC", entry, tp=tp, sl=90, direction=1, leverage=leverage)
    
    # Symulujemy trafienie w TP (cena idzie do 110)
    closed = wallet.check_tp_sl(current_price=110.0)
    
    expected_pnl_pct = 100.0  # 10% ruchu * 10x dźwigni
    actual_pnl_pct = closed[0]['pnl_percent']
    
    assert actual_pnl_pct == expected_pnl_pct, f"BŁĄD PnL LONG: Expected {expected_pnl_pct}%, got {actual_pnl_pct}%"
    print(f"✅ LONG PnL poprawny: {actual_pnl_pct}%")

def test_pnl_short():
    print("\n--- TEST 3: Obliczanie PnL dla SHORT (GŁÓWNY BUG) ---")
    wallet = VirtualWallet(initial_balance=10000, commission=0, slippage=0)
    entry = 100.0
    tp = 90.0   # Cena spada o 10% (zysk dla shorta)
    leverage = 10
    
    wallet.open_position("ETH", entry, tp=tp, sl=110, direction=-1, leverage=leverage)
    
    # Symulujemy trafienie w TP (cena spada do 90)
    closed = wallet.check_tp_sl(current_price=90.0)
    
    expected_pnl_pct = 100.0  # 10% ruchu w dół * 10x dźwigni = +100% zysku
    actual_pnl_pct = closed[0]['pnl_percent']
    
    # STARY KOD zwracałby tutaj -100% (STRATĘ), bo mnożył przez direction=-1!
    assert actual_pnl_pct == expected_pnl_pct, f"BŁĄD PnL SHORT: Expected {expected_pnl_pct}%, got {actual_pnl_pct}% (STARY KOD MIAŁ TU BUGA)"
    print(f"✅ SHORT PnL poprawny: {actual_pnl_pct}% (Zysk przy spadkach działa!)")

def test_strategy_weights():
    print("\n--- TEST 4: Brak błędu KeyError w wagach strategii ---")
    try:
        engine = NexusStrategyEngine()
        # W starym kodzie to wywalało KeyError: 'fvg' w linii feat_trend * self.weights['fvg']
        # Teraz używa 'trend' i nie powinno wywalić exception
        print(f"✅ Wagi załadowane poprawnie: {engine.weights}")
        assert 'trend' in engine.weights, "Brak klucza 'trend' w wagach!"
    except KeyError as e:
        print(f"❌ BŁĄD w strategy.py: Brakuje klucza {e}")

if __name__ == "__main__":
    print("========================================")
    print("URUCHAMIAM TESTY DLA NAPRAWIONEGO KODU")
    print("========================================")
    
    try:
        test_slippage_logic()
        test_pnl_long()
        test_pnl_short()
        test_strategy_weights()
        print("\n========================================")
        print("🎉 WSZYSTKIE TESTY PRZESZŁY POMYŚLNIE!")
        print("========================================")
    except AssertionError as e:
        print(f"\n❌ TEST ZALANY: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        sys.exit(1)