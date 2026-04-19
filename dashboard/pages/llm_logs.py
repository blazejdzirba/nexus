import streamlit as st
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.llm.llm_manager import LLMManager

st.set_page_config(page_title="Logi LLM", layout="wide")
st.title("📜 Pełna historia promptów i odpowiedzi LLM")

llm = LLMManager()
date = st.date_input("Data", value=pd.Timestamp.now())
logs = llm.get_logs(date.strftime("%Y-%m-%d"), limit=200)

if logs:
    for log in logs:
        with st.expander(f"{log['timestamp']} | {log['context'].get('symbol', '?')} | Odpowiedź: {log['response'][:50] if log['response'] else 'brak'}"):
            st.json(log)
else:
    st.info("Brak logów")