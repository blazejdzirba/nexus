from core.engine.trade_manager import VirtualWallet

class VirtualWallet:
    def __init__(self, initial_balance=10000.0, slippage=0.001, commission=0.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.slippage = slippage
        self.commission = commission
        self.active_positions = []
        self.history = []

    def open_position(self, symbol, entry_price, tp, sl, direction=1):
        # FIX 1: POPRAWNY SLIPPAGE
        if direction == 1:  # LONG
            actual_entry = entry_price * (1 + self.slippage)
        else:  # SHORT
            actual_entry = entry_price * (1 - self.slippage)
        
        self.balance -= 100 # Uproszczenie: każda pozycja kosztuje 100$         
        self.active_positions.append({
            'symbol': symbol, 'entry': actual_entry, 'tp': tp, 'sl': sl,
            'direction': direction, 'size_usd': 100, 'leverage': 10
        })

    def check_tp_sl(self, current_price):
        closed = []
        for pos in self.active_positions[:]:
            hit_tp = current_price >= pos['tp'] if pos['direction'] == 1 else current_price <= pos['tp']
            hit_sl = current_price <= pos['sl'] if pos['direction'] == 1 else current_price >= pos['sl']

            reason = None
            exit_price = current_price
            
            if hit_tp:
                reason = "TP"
                exit_price = pos['tp']
            elif hit_sl:
                reason = "SL"
                exit_price = pos['sl']

            if reason:
                # FIX 2: POPRAWNY PNL DLA SHORTA
                if pos['direction'] == 1:  # LONG
                    pnl_pct = ((exit_price - pos['entry']) / pos['entry']) * 100 * pos['leverage']
                else:  # SHORT
                    pnl_pct = ((pos['entry'] - exit_price) / pos['entry']) * 100 * pos['leverage']
                
                self.balance += 100 + (100 * (pnl_pct / 100))
                self.history.append({'symbol': pos['symbol'], 'pnl': round(pnl_pct, 2), 'reason': reason})
                self.active_positions.remove(pos)
                closed.append(self.history[-1])
        return closed

# ==========================================
# POCZĄTEK TESTÓW
# ==========================================
print("Start testów...\n")

wallet = VirtualWallet()

# TEST 1: Slippage dla LONGA
wallet.open_position("BTC", 100.0, 110.0, 90.0, direction=1)
long_entry = wallet.active_positions[0]['entry']
print(f"1. Slippage LONG: Cena wejścia to {long_entry} (Oczekiwane: 100.1) -> {'✅ ZDANY' if long_entry == 100.1 else '❌ OPADŁ'}")

# TEST 2: Slippage dla SHORTA
wallet.active_positions.clear()
wallet.open_position("ETH", 100.0, 90.0, 110.0, direction=-1)
short_entry = wallet.active_positions[0]['entry']
print(f"2. Slippage SHORT: Cena wejścia to {short_entry} (Oczekiwane: 99.9) -> {'✅ ZDANY' if short_entry == 99.9 else '❌ OPADŁ'}")

# TEST 3: PnL dla LONGA (cena idzie w górę, zysk)
wallet.active_positions.clear()
wallet.open_position("SOL", 100.0, 110.0, 90.0, direction=1)
res_long = wallet.check_tp_sl(110.0)[0]
print(f"3. PnL LONG (cena +10%, 10x leverage): Wynik to {res_long['pnl']}% (Oczekiwane: ~100%) -> {'✅ ZDANY' if res_long['pnl'] > 95 else '❌ OPADŁ'}")

# TEST 4: PnL dla SHORTA (cena idzie w dół, zysk) - TUTAJ BYŁ GŁÓWNY BUG
wallet.active_positions.clear()
wallet.open_position("BNB", 100.0, 90.0, 110.0, direction=-1)
res_short = wallet.check_tp_sl(90.0)[0]
print(f"4. PnL SHORT (cena -10%, 10x leverage): Wynik to {res_short['pnl']}% (Oczekiwane: ~100%) -> {'✅ ZDANY' if res_short['pnl'] > 95 else '❌ OPADŁ - STARY KOD DAŁBY TUTAJ -100%!'}")

# TEST 5: PnL dla SHORTA (cena idzie w górę, strata)
wallet.active_positions.clear()
wallet.open_position("XRP", 100.0, 90.0, 110.0, direction=-1)
res_short_loss = wallet.check_tp_sl(110.0)[0]
print(f"5. PnL SHORT (cena +10%, 10x leverage): Wynik to {res_short_loss['pnl']}% (Oczekiwane: ~-100%) -> {'✅ ZDANY' if res_short_loss['pnl'] < -95 else '❌ OPADŁ'}")

print("\n========================================")
if all(['✅' in str(v) for v in [long_entry, short_entry, res_long['pnl'], res_short['pnl'], res_short_loss['pnl']]]):
    print("🎉 WSZYSTKIE TESTY MATMA TYLKO PRZESZŁY!")
else:
    print("Coś jest nie tak z logiką.")