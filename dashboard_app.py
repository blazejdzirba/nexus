import streamlit as st
import os
import sys

# WYMUSZENIE ŚCIEŻKI GŁÓWNEJ
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import pandas as pd
# Teraz importy powinny przejść bez błędu
from backtester import run_multi_backtest
from config import Config
import streamlit as st
import pandas as pd
import json
import os
import glob
import plotly.graph_objects as go
import duckdb
from datetime import datetime, timedelta

from core.engine.strategy import NexusStrategyEngine
from backtester import run_multi_backtest
from config import Config

st.set_page_config(page_title="NEXUS-AI Control Center", layout="wide")

# ------------------------------------------------------------------
# FUNKCJE POMOCNICZE I PRESETY
# ------------------------------------------------------------------
PRESETS_FILE = os.path.join(Config.BASE_DIR, "presets.json")

def load_virtual_portfolio():
    path = os.path.join(Config.LOGS_DIR, "virtual_portfolio.json")
    if os.path.exists(path):
        with open(path, 'r') as f: return json.load(f)
    return {"balance": 10000.0, "active_trades": [], "history": []}

def load_parquet_safe(path: str) -> pd.DataFrame:
    for engine in ['pyarrow', 'fastparquet']:
        try:
            return pd.read_parquet(path, engine=engine)
        except Exception: continue
    st.error(f"Nie można odczytać pliku: {os.path.basename(path)}")
    return pd.DataFrame()

def save_presets(preset_dict):
    with open(PRESETS_FILE, 'w') as f:
        json.dump(preset_dict, f, indent=4)
    st.toast("✅ Preset zapisany pomyślnie!")

def load_presets():
    if os.path.exists(PRESETS_FILE):
        with open(PRESETS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Inicjalizacja stanu dla presetów
if 'current_preset' not in st.session_state:
    st.session_state.current_preset = load_presets()

def get_preset_val(key, default):
    return st.session_state.current_preset.get(key, default)

# ------------------------------------------------------------------
# MENU GŁÓWNE
# ------------------------------------------------------------------
st.title("🧠 NEXUS-AI: System Operacyjny & Backtester")

tab1, tab2, tab3 = st.tabs(["📈 Monitoring Skanera (LIVE)", "🧪 Zaawansowany Backtester", "🔍 Data Inspector"])

# ------------------------------------------------------------------
# ZAKŁADKA 1: MONITORING
# ------------------------------------------------------------------
with tab1:
    st.header("Sytuacja w Wirtualnym Portfelu")
    auto_refresh = st.toggle("Auto-refresh (60s)", value=False)
    if auto_refresh:
        import time
        st.markdown(f"_Ostatnia aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')}_")
        time.sleep(60)
        st.rerun()

    data = load_virtual_portfolio()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo całkowite", f"{data['balance']:.2f} USDT")
    c2.metric("Otwarte pozycje", len(data['active_trades']))

    if data['history']:
        wins = len([t for t in data['history'] if t.get('pnl_pct', t.get('pnl_percent', 0)) > 0])
        wr = (wins / len(data['history'])) * 100
        c3.metric("Win Rate", f"{wr:.1f}%")
        total_pnl = sum(t.get('pnl_usd', 0) for t in data['history'])
        c4.metric("Łączny PnL", f"{total_pnl:.2f} USDT", delta=f"{total_pnl:.2f}")
    else:
        c3.metric("Win Rate", "0%")
        c4.metric("Łączny PnL", "0.00 USDT")

    if data['active_trades']:
        st.subheader("🔥 Aktywne Pozycje")
        st.dataframe(pd.DataFrame(data['active_trades']), use_container_width=True)

    if data['history']:
        st.subheader("📜 Ostatnie zamknięte transakcje")
        df_hist = pd.DataFrame(data['history']).tail(20)
        st.dataframe(df_hist, use_container_width=True)

# ------------------------------------------------------------------
# ZAKŁADKA 2: TESTER PARAMETRÓW (BACKTESTER)
# ------------------------------------------------------------------
with tab2:
    st.header("Konfiguracja Strategii & Backtest")

    col_left, col_right = st.columns([1, 3])

    with col_left:
        all_files = glob.glob(os.path.join(Config.DATA_DIR, "*.parquet")) + glob.glob(os.path.join(Config.DATA_DIR, "**", "*.parquet"), recursive=True)
        available_symbols = sorted(set(os.path.basename(f).split('_')[0] for f in all_files)) or ["BTCUSDT"]
        
        selected_symbol = st.selectbox("Symbol", available_symbols)
        date_range = st.date_input("Zakres dat", [datetime.now() - timedelta(days=7), datetime.now()])
        
        st.subheader("⚙️ Parametry")
        with st.expander("Wagi Sygnałów AI", expanded=True):
            fvg_w = st.slider("Waga FVG", 0.0, 1.0, get_preset_val('fvg_w', 0.40))
            pvsra_w = st.slider("Waga PVSRA", 0.0, 1.0, get_preset_val('pvsra_w', 0.35))
            rsi_w = st.slider("Waga RSI", 0.0, 1.0, get_preset_val('rsi_w', 0.15))
            ai_threshold = st.slider("AI Confidence Threshold", 10, 100, get_preset_val('ai_threshold', 60))

        with st.expander("Wskaźniki Techniczne"):
            rsi_len = st.number_input("RSI Length", min_value=2, max_value=50, value=get_preset_val('rsi_len', 14))
            ema_fast = st.number_input("EMA Fast", min_value=5, max_value=100, value=get_preset_val('ema_fast', 21))
            ema_slow = st.number_input("EMA Slow", min_value=20, max_value=200, value=get_preset_val('ema_slow', 55))
            atr_len = st.number_input("ATR Length", min_value=5, max_value=50, value=get_preset_val('atr_len', 14))

        with st.expander("Zarządzanie Ryzykiem"):
            sl_pct = st.number_input("Stop Loss (%)", min_value=0.1, max_value=50.0, value=get_preset_val('sl_pct', 5.0), step=0.1)
            tp_pct = st.number_input("Take Profit (%)", min_value=0.1, max_value=100.0, value=get_preset_val('tp_pct', 2.5), step=0.1)
            leverage = st.number_input("Dźwignia", min_value=1, max_value=100, value=get_preset_val('leverage', 10))
            
        if st.button("💾 Zapisz jako Preset"):
            current_config = {
                'fvg_w': fvg_w, 'pvsra_w': pvsra_w, 'rsi_w': rsi_w, 'ai_threshold': ai_threshold,
                'rsi_len': rsi_len, 'ema_fast': ema_fast, 'ema_slow': ema_slow, 'atr_len': atr_len,
                'sl_pct': sl_pct, 'tp_pct': tp_pct, 'leverage': leverage
            }
            save_presets(current_config)

    with col_right:
        if st.button("🚀 URUCHOM BACKTEST (Pełny cykl)", type="primary"):
            if len(date_range) != 2:
                st.error("Wybierz poprawny zakres dat.")
            else:
                with st.spinner("Przetwarzanie danych..."):
                    # Przygotowanie parametrów dla logiki
                    strategy_params = {
                        'weights': {'fvg': fvg_w, 'pvsra': pvsra_w, 'rsi': rsi_w, 'mfi': 0.1},
                        'ai_threshold': ai_threshold,
                        'rsi_length': rsi_len, 'hts_fast_len': ema_fast, 'hts_slow_len': ema_slow, 'atr_len': atr_len
                    }
                    wallet_params = {
                        'sl_percent': sl_pct, 'tp_percent': tp_pct, 'leverage': leverage,
                        'initial_balance': 10000, 'risk_per_trade': 2.0
                    }
                    
                    start_str, end_str = date_range[0].strftime("%Y-%m-%d"), date_range[1].strftime("%Y-%m-%d")
                    trades_df, equity_df, signals_df = run_multi_backtest(
                        [selected_symbol], Config.DATA_DIR, start_str, end_str, strategy_params, wallet_params
                    )
                    
                    if trades_df.empty:
                        st.warning("Brak transakcji w podanym okresie.")
                    else:
                        st.success(f"Ukończono! Wykonano {len(trades_df)} transakcji.")
                        
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Początkowe Equity", "10,000 USDT")
                        m2.metric("Końcowe Equity", f"{equity_df['balance'].iloc[-1]:.2f} USDT")
                        wins = len(trades_df[trades_df['pnl_percent'] > 0])
                        m3.metric("Win Rate", f"{(wins / len(trades_df)) * 100:.1f}%")
                        m4.metric("Max Drawdown", "W budowie")

                        # Wykres Equity
                        fig_eq = go.Figure()
                        fig_eq.add_trace(go.Scatter(x=equity_df['timestamp'], y=equity_df['balance'], fill='tozeroy', name='Equity'))
                        fig_eq.update_layout(title="Krzywa Kapitału (Equity)", template="plotly_dark", height=300)
                        st.plotly_chart(fig_eq, use_container_width=True)

                        # Wykres Cenowy ze znacznikami
                        fig_price = go.Figure()
                        fig_price.add_trace(go.Scatter(x=signals_df['timestamp'], y=signals_df['close'], name='Cena', line=dict(color='gray', width=1)))
                        
                        longs = trades_df[trades_df['direction'] == 1]
                        shorts = trades_df[trades_df['direction'] == -1]
                        
                        fig_price.add_trace(go.Scatter(x=longs['entry_time'], y=longs['entry_price'], mode='markers', name='Wejście LONG', marker=dict(color='lime', symbol='triangle-up', size=12)))
                        fig_price.add_trace(go.Scatter(x=shorts['entry_time'], y=shorts['entry_price'], mode='markers', name='Wejście SHORT', marker=dict(color='red', symbol='triangle-down', size=12)))

                        fig_price.update_layout(title=f"{selected_symbol} - Analiza Wejść", template="plotly_dark", height=500)
                        st.plotly_chart(fig_price, use_container_width=True)

                        # Eksport raportu
                        csv_data = signals_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Eksportuj pełne dane świec i sygnałów (CSV)",
                            data=csv_data,
                            file_name=f"nexus_report_{selected_symbol}.csv",
                            mime="text/csv",
                        )

# ------------------------------------------------------------------
# ZAKŁADKA 3: DATA INSPECTOR
# ------------------------------------------------------------------
with tab3:
    st.header("🔍 Inspekcja Bazy Danych / Sygnałów")
    st.markdown("Przeglądaj wygenerowane sygnały bez pisania zapytań SQL.")
    
    try:
        conn = duckdb.connect("backtest_results.duckdb")
        tables = conn.execute("SHOW TABLES").fetchdf()
        
        if tables.empty or 'signals' not in tables['name'].values:
            st.info("Brak tabeli 'signals' w bazie. Wykonaj najpierw Backtest.")
        else:
            limit = st.slider("Liczba wierszy do podglądu", 100, 10000, 500)
            df_view = conn.execute(f"SELECT * FROM signals ORDER BY timestamp DESC LIMIT {limit}").fetchdf()
            
            st.dataframe(df_view, use_container_width=True)
            
            # Przycisk do zrzutu do Excela (tylko podgląd, dla uniknięcia wieszania przeglądarki)
            st.download_button(
                label="📥 Pobierz widok jako CSV",
                data=df_view.to_csv(index=False).encode('utf-8'),
                file_name="inspector_view.csv",
                mime="text/csv",
            )
    except Exception as e:
        st.error(f"Błąd połączenia z bazą: {e}")
    finally:
        if 'conn' in locals():
            conn.close()