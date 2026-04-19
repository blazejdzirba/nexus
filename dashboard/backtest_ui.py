import os
import sys
import glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ← FIX: backtest_ui.py jest w dashboard/, musimy dodać root projektu do ścieżki
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backtester import run_multi_backtest
from config import Config

st.set_page_config(layout="wide", page_title="NEXUS-AI Backtest Studio")
st.title("🧪 NEXUS-AI Backtest Studio")

with st.sidebar:
    st.header("Parametry symulacji")

    # ← FIX: szukamy plików parquet w katalogu danych (flat + partycjonowane)
    parquet_files = glob.glob(os.path.join(Config.DATA_DIR, "*.parquet")) + \
                    glob.glob(os.path.join(Config.DATA_DIR, "**", "*.parquet"), recursive=True)

    all_symbols = sorted(set(
        os.path.basename(f).split('_')[0]
        for f in parquet_files
        if not os.path.basename(f).startswith('.')
    ))

    if not all_symbols:
        st.warning("Brak plików .parquet w katalogu danych. Pobierz dane przez download_historical.py")
        selected_symbols = []
    else:
        selected_symbols = st.multiselect("Pary (max 10)", all_symbols, default=all_symbols[:min(3, len(all_symbols))])

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Od", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("Do", datetime.now())

    st.subheader("Strategia")
    ai_threshold = st.slider("Próg AI confidence (%)", 0, 100, 60)
    use_fvg = st.checkbox("FVG", True)
    use_pvsra = st.checkbox("PVSRA", True)

    st.subheader("Zarządzanie ryzykiem")
    initial_balance = st.number_input("Kapitał początkowy (USDT)", 1000, 100000, 10000)
    risk_per_trade = st.slider("Ryzyko na trade (% kapitału)", 0.5, 10.0, 2.0)
    max_positions = st.slider("Maks. jednoczesnych pozycji", 1, 20, 5)
    leverage = st.slider("Dźwignia", 1, 50, 10)

    st.subheader("Zaawansowane")
    commission = st.number_input("Prowizja (%)", 0.01, 0.5, 0.1) / 100
    slippage = st.number_input("Poślizg (%)", 0.0, 1.0, 0.05) / 100

if st.button("🚀 Uruchom backtest wielowątkowy"):
    if not selected_symbols:
        st.warning("Wybierz przynajmniej jedną parę.")
    else:
        with st.spinner("Backtesting w toku..."):
            strategy_params = {
                'ai_threshold': ai_threshold,
                'use_fvg': use_fvg,
                'use_pvsra': use_pvsra,
            }
            wallet_params = {
                'initial_balance': initial_balance,
                'risk_per_trade': risk_per_trade,
                'max_positions': max_positions,
                'leverage': leverage,
                'commission': commission,
                'slippage': slippage,
            }
            trades_df, equity_df = run_multi_backtest(
                symbols=selected_symbols,
                data_dir=Config.DATA_DIR,
                start_date=str(start_date),
                end_date=str(end_date),
                strategy_params=strategy_params,
                wallet_params=wallet_params,
                max_workers=4
            )

        if trades_df.empty:
            st.warning("Brak transakcji w tym przedziale. Spróbuj niższy próg AI lub dłuższy zakres dat.")
        else:
            st.success(f"✅ Ukończono. Liczba transakcji: {len(trades_df)}")

            col1, col2, col3 = st.columns(3)
            final_balance = equity_df['balance'].iloc[-1] if not equity_df.empty else initial_balance
            total_pnl = final_balance - initial_balance
            win_rate = (trades_df['pnl_percent'] > 0).mean() * 100 if not trades_df.empty else 0

            col1.metric("Końcowe saldo", f"{final_balance:.2f} USDT")
            col2.metric("Win Rate", f"{win_rate:.1f}%")
            col3.metric("Całkowity PnL", f"{total_pnl:.2f} USDT",
                        delta=f"{total_pnl / initial_balance * 100:.1f}%")

            # Wykres equity curve
            if not equity_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=equity_df['timestamp'], y=equity_df['balance'],
                    mode='lines', name='Equity', line=dict(color='#00ff88')
                ))
                fig.add_hline(y=initial_balance, line_dash="dash", line_color="gray",
                              annotation_text="Start")
                fig.update_layout(
                    title="Krzywa kapitału",
                    template="plotly_dark",
                    height=400,
                    xaxis_title="Czas",
                    yaxis_title="Saldo (USDT)"
                )
                st.plotly_chart(fig, use_container_width=True)

            # Tabela transakcji
            st.subheader("Lista transakcji")
            cols_to_show = [c for c in ['symbol', 'entry_time', 'exit_time', 'direction',
                                         'entry_price', 'exit_price', 'pnl_percent',
                                         'pnl_usd', 'exit_reason'] if c in trades_df.columns]
            st.dataframe(trades_df[cols_to_show], use_container_width=True)