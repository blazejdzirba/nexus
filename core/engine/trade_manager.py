import json
import os
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class VirtualWallet:
    """
    Portfel wirtualny – działa w trybie LIVE i BACKTEST.
    """
    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_per_trade: float = 2.0,       
        max_positions: int = 5,
        leverage: int = 10,
        commission: float = 0.001,          
        slippage: float = 0.0005,           
        live_mode: bool = False             
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.max_positions = max_positions
        self.leverage = leverage
        self.commission = commission
        self.slippage = slippage
        self.live_mode = live_mode

        self.active_positions = []
        self.history = []

        if self.live_mode:
            self.state_file = os.path.join(Config.LOGS_DIR, "virtual_portfolio.json")
            self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.balance = data.get('balance', self.initial_balance)
                    self.active_positions = data.get('active_trades', [])
                    self.history = data.get('history', [])
            except json.JSONDecodeError as e:
                logger.error(f"Błąd wczytywania stanu portfela: {e}")

    def _save_state(self):
        if not self.live_mode:
            return
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump({
                'balance': self.balance,
                'active_trades': self.active_positions,
                'history': self.history
            }, f, indent=4)

    # FIX: Dodano leverage=None dla kompatybilności wstecznej z backtesterem
    def open_position(self, symbol, entry_price, tp, sl, direction=1, timestamp=None, leverage=None):
        if len(self.active_positions) >= self.max_positions:
            return False
        if any(p['symbol'] == symbol for p in self.active_positions):
            return False

        # POPRAWKA 1: Poprawny Slippage 
        if direction == 1:  # LONG
            actual_entry = entry_price * (1 + self.slippage)
        else:  # SHORT
            actual_entry = entry_price * (1 - self.slippage)
        
        position_size_usd = self.balance * (self.risk_per_trade / 100)
        commission_cost = position_size_usd * self.commission

        if self.balance < position_size_usd + commission_cost:
            return False

        self.balance -= (position_size_usd + commission_cost)

        # POPRAWKA 2: Przeliczenie TP i SL bazując na actual_entry
        if direction == 1:  # LONG
            actual_tp = actual_entry + (tp - entry_price)
            actual_sl = actual_entry - (entry_price - sl)
        else:  # SHORT
            actual_tp = actual_entry - (entry_price - tp)
            actual_sl = actual_entry + (sl - entry_price)

        self.active_positions.append({
            'symbol': symbol,
            'entry': actual_entry,
            'tp': actual_tp,
            'sl': actual_sl,
            'direction': direction,
            'size_usd': position_size_usd,
            'leverage': self.leverage,  # Zawsze używamy dźwigni z init
            'open_time': str(timestamp or datetime.now().isoformat()),
        })

        self._save_state()
        return True

    def open_trade(self, symbol, price, direction, sl_percent, tp1_percent,
                   tp2_percent, tp3_percent, amount_usd=100):
        tp = price * (1 + tp1_percent / 100 * direction)
        sl = price * (1 - sl_percent / 100 * direction)
        return self.open_position(symbol, price, tp, sl, direction)

    def check_tp_sl(self, current_price: float, timestamp=None) -> list:
        closed = []
        for pos in self.active_positions[:]:
            hit_tp = current_price >= pos['tp'] if pos['direction'] == 1 else current_price <= pos['tp']
            hit_sl = current_price <= pos['sl'] if pos['direction'] == 1 else current_price >= pos['sl']

            reason = None
            exit_price = current_price
            
            if hit_tp:
                reason = "TP1"
                exit_price = pos['tp'] 
            elif hit_sl:
                reason = "SL"
                exit_price = pos['sl'] 

            if reason:
                # POPRAWKA 3: Bezpieczne obliczanie PnL
                if pos['direction'] == 1:  # LONG
                    pnl_pct = ((exit_price - pos['entry']) / pos['entry']) * 100 * pos['leverage']
                else:  # SHORT
                    pnl_pct = ((pos['entry'] - exit_price) / pos['entry']) * 100 * pos['leverage']
                
                commission_cost = pos['size_usd'] * self.commission
                pnl_usd = pos['size_usd'] * (pnl_pct / 100) - commission_cost
                self.balance += pos['size_usd'] + pnl_usd

                trade_record = {
                    'symbol': pos['symbol'],
                    'entry_time': pos['open_time'],
                    'exit_time': str(timestamp or datetime.now().isoformat()),
                    'direction': pos['direction'],
                    'entry_price': pos['entry'],
                    'exit_price': exit_price,
                    'pnl_percent': round(pnl_pct, 4),
                    'pnl_usd': round(pnl_usd, 2),
                    'exit_reason': reason,
                }
                self.history.append(trade_record)
                self.active_positions.remove(pos)
                closed.append(trade_record)

        if closed:
            self._save_state()
        return closed

    def update_and_check(self, current_prices: dict):
        for pos in self.active_positions[:]:
            symbol = pos['symbol']
            if symbol not in current_prices:
                continue
            price = current_prices[symbol]
            self.check_tp_sl(price)

    @property
    def win_rate(self) -> float:
        if not self.history:
            return 0.0
        wins = sum(1 for t in self.history if t['pnl_percent'] > 0)
        return wins / len(self.history) * 100

    @property
    def total_pnl(self) -> float:
        return self.balance - self.initial_balance

    def __repr__(self):
        return (f"VirtualWallet(balance={self.balance:.2f}, "
                f"positions={len(self.active_positions)}, "
                f"trades={len(self.history)}, WR={self.win_rate:.1f}%)")