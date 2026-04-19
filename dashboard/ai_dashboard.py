import streamlit as st
import pandas as pd
import sys
import os
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.llm_manager import LLMManager
from core.llm.prompt_templates import DEFAULT_SYSTEM_PROMPT
from core.api.data_feed import BybitDataFeed
from core.engine.strategy import NexusStrategyEngine
from core.engine.trade_manager import VirtualWallet
from config import Config

st.set_page_config(page_title="NEXUS-AI Control Center", layout="wide")

# ====================== FUNKCJA POMOCNICZA ======================
def get_available_symbols():
    """Zwraca listę symboli dostępnych w plikach Parquet."""
    symbols = set()
    parquet_files = glob.glob(os.path.join(Config.DATA_DIR, "*.parquet")) + \
                    glob.glob(os.path.join(Config.DATA_DIR, "**", "*.parquet"), recursive=True)
    for f in parquet_files:
        name = os.path.basename(f).split('_')[0]
        symbols.add(name)
    return sorted(symbols) if symbols else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# ====================== INICJALIZACJA STANU ======================
if 'llm_manager' not in st.session_state:
    st.session_state.llm_manager = LLMManager(log_dir="logs/llm")
    st.session_state.llm_manager.set_system_prompt(DEFAULT_SYSTEM_PROMPT)
if 'strategy_engine' not in st.session_state:
    st.session_state.strategy_engine = NexusStrategyEngine()
if 'wallet' not in st.session_state:
    st.session_state.wallet = VirtualWallet(live_mode=True)

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("⚙️ Konfiguracja LLM")
    system_prompt = st.text_area("System Prompt", value=DEFAULT_SYSTEM_PROMPT, height=200)
    if st.button("Zapisz system prompt"):
        st.session_state.llm_manager.set_system_prompt(system_prompt)
        st.success("Zapisano!")
    
    st.divider()
    st.header("💰 Parametry strategii")
    ai_threshold = st.slider("Próg AI confidence", 0, 100, 60)
    use_cache = st.checkbox("Użyj cache LLM", value=True)
    
    if st.button("Wyczyść cache LLM"):
        st.session_state.llm_manager.cache.clear()
        st.success("Cache wyczyszczony!")

# ====================== GŁÓWNY PANEL ======================
tab1, tab2, tab3 = st.tabs(["📈 Test sygnału", "🤖 Decyzje LLM", "📊 Portfel"])

with tab1:
    st.header("Test sygnału z RAG i cache")
    
    # 🔁 Dynamiczna lista symboli
    symbols = get_available_symbols()
    symbol = st.selectbox("Symbol", symbols)
    
    if st.button("Pobierz i analizuj"):
        feed = BybitDataFeed()
        df = feed.fetch_historical_klines(symbol, interval="5", limit=50)
        if df is not None and not df.empty:
            try:
                df = st.session_state.strategy_engine.calculate_signals(df)
                last = df.iloc[-1]
                
                st.metric("Cena", f"{last['close']:.2f}")
                st.metric("AI Confidence", f"{last['ai_confidence']:.1f}%")
                st.metric("Setup Bullish", last.get('setup_bullish', False))
                st.metric("Setup Bearish", last.get('setup_bearish', False))
                
                if last.get('setup_bullish') and last['ai_confidence'] >= ai_threshold:
                    st.success("🚀 Sygnał LONG! Pytam LLM...")
                    
                    market_context = f"Price: {last['close']}, RSI: {last.get('rsi', 50):.1f}, Volume climax: {last.get('pvsra_climax', False)}"
                    
                    with st.spinner("LLM analizuje (RAG + cache)..."):
                        result = st.session_state.llm_manager.ask_with_rag(
                            symbol=symbol,
                            signal_score=last.get('nexus_score', 0),
                            market_context=market_context,
                            use_cache=use_cache
                        )
                    
                    st.info(f"📦 Cache: {'TAK' if result.get('from_cache') else 'NIE'}")
                    st.success(f"🤖 Decyzja: {result['decision']}")
                    if result['sl'] > 0:
                        st.metric("Sugerowany SL", f"{result['sl']}%")
                    st.text_area("Odpowiedź surowa", result['raw_response'], height=150)
                else:
                    st.warning("Brak sygnału lub AI confidence poniżej progu")
            except Exception as e:
                st.error(f"Błąd obliczeń: {e}")
        else:
            st.error("Brak danych dla symbolu")

with tab2:
    st.header("Historia zapytań do LLM")
    log_date = st.date_input("Data", value=pd.Timestamp.now())
    logs = st.session_state.llm_manager.get_logs(date=log_date.strftime("%Y-%m-%d"), limit=50)
    if logs:
        for log in reversed(logs[-10:]):
            with st.expander(f"{log['timestamp']} | {log.get('symbol', '?')} | Score: {log.get('signal_score', 0)}"):
                st.markdown("**Kontekst rynkowy:**")
                st.code(log.get('market_context', ''))
                st.markdown("**RAG (podobne transakcje):**")
                st.code(log.get('historical_matches', '')[:500])
                st.markdown("**Odpowiedź LLM:**")
                st.code(log.get('response', 'Brak'))
    else:
        st.info("Brak logów")

with tab3:
    st.header("Stan portfela")
    wallet = st.session_state.wallet
    col1, col2, col3 = st.columns(3)
    col1.metric("Saldo", f"{wallet.balance:.2f} USDT")
    col2.metric("Otwarte pozycje", len(wallet.active_positions))
    col3.metric("Win Rate", f"{wallet.win_rate:.1f}%")
    
    if wallet.active_positions:
        st.subheader("Aktywne pozycje")
        st.dataframe(pd.DataFrame(wallet.active_positions))
    
    if wallet.history:
        st.subheader("Ostatnie transakcje")
        st.dataframe(pd.DataFrame(wallet.history).tail(10))