import duckdb
import pandas as pd

conn = duckdb.connect("backtest_results.duckdb")

# Sprawdź tabele
tables = conn.execute("SHOW TABLES").fetchdf()
print("Tabele:", tables['name'].tolist())

# Eksportuj trades
trades = conn.execute("SELECT * FROM trades").fetchdf()
if not trades.empty:
    trades.to_csv("trades.csv", index=False)
    print(f"\n✅ Zapisano {len(trades)} transakcji do trades.csv")
    print("\nPierwsze 5 transakcji:")
    print(trades[['symbol', 'entry_time', 'direction', 'entry_price', 'exit_price', 'pnl_percent', 'exit_reason']].head())
else:
    print("❌ Brak transakcji w bazie")

# Eksportuj equity
equity = conn.execute("SELECT * FROM equity").fetchdf()
if not equity.empty:
    equity.to_csv("equity.csv", index=False)
    print(f"\n✅ Zapisano {len(equity)} punktów equity do equity.csv")
    
    # Podstawowe statystyki
    start_balance = equity.iloc[0]['balance']
    end_balance = equity.iloc[-1]['balance']
    max_balance = equity['balance'].max()
    min_balance = equity['balance'].min()
    drawdown = (max_balance - min_balance) / max_balance * 100
    
    print(f"\n📊 Statystyki:")
    print(f"   Kapitał początkowy: {start_balance:.2f} USDT")
    print(f"   Kapitał końcowy: {end_balance:.2f} USDT")
    print(f"   Zysk/Strata: {end_balance - start_balance:.2f} USDT")
    print(f"   Max drawdown: {drawdown:.1f}%")

conn.close()