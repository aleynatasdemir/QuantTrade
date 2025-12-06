"""
REALISTIC SLOT-BASED BACKTESTER (OPTIMIZED HYBRID EXIT)
"""

import pandas as pd
import numpy as np
import joblib
from catboost import CatBoostClassifier
import glob, os
import matplotlib.pyplot as plt
from train_model import SectorStandardScaler  # sadece scaler kullanıyoruz

# ===== CONFIG =====
DATA_PATH   = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_final"

HORIZON      = 20        # Maksimum tutma süresi
STOP_LOSS    = -0.05     # -%5 Hard Stop
TAKE_PROFIT  = 0.10      # +%10
MAX_POSITIONS = 5        
INITIAL_CAPITAL = 100_000
COMMISSION   = 0.002     # Binde 2

# Slipaj
SLIPPAGE_BUY  = 0.01   # %1
SLIPPAGE_SELL = 0.005  # %0.5 

PRICE_COL  = "price_close"
OPEN_COL   = "price_open"
LOW_COL    = "price_low"
HIGH_COL   = "price_high"
DATE_COL   = "date"
SYMBOL_COL = "symbol"
SECTOR_COL = "sector"
TOP_K = 5 

def get_latest(pattern):
    files = glob.glob(pattern)
    if not files: return None
    return max(files, key=os.path.getmtime)

def load_model_and_meta():
    model_path = get_latest(os.path.join(RESULTS_DIR, "catboost_alpha20d_*.cbm"))
    meta_path  = get_latest(os.path.join(RESULTS_DIR, "neutralizer_alpha20d_*.pkl"))
    if not model_path or not meta_path: raise FileNotFoundError("Model dosyaları yok.")
    
    model = CatBoostClassifier()
    model.load_model(model_path)
    meta = joblib.load(meta_path)
    return model, meta

# ======================================================
# 1. ADIM: İNDİKATÖRLERİ HESAPLA (VERİ MUTFAĞI)
# ======================================================
def calculate_stagnation_indicators(df):
    """
    Backtest döngüsü başlamadan önce tüm veri setine
    Durgunluk (Stagnation) ve Zayıflık (RS Weakness) etiketlerini basar.
    """
    print(">> Calculating Technical Indicators (Smart Exits)...")
    df = df.sort_values([SYMBOL_COL, DATE_COL])
    
    # --- Volatilite ve Trend Hesabı ---
    # True Range
    df['tr0'] = abs(df[HIGH_COL] - df[LOW_COL])
    df['tr1'] = abs(df[HIGH_COL] - df[PRICE_COL].shift(1))
    df['tr2'] = abs(df[LOW_COL] - df[PRICE_COL].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    
    # ATR (14)
    df['atr'] = df.groupby(SYMBOL_COL)['tr'].transform(lambda x: x.rolling(14).mean())
    
    # Normalized ATR (NATR) -> Volatilite %'si
    df['natr'] = (df['atr'] / df[PRICE_COL]) * 100
    
    # Trend Sapması (Fiyat 20 günlük ortalamadan ne kadar uzak?)
    df['sma20'] = df.groupby(SYMBOL_COL)[PRICE_COL].transform(lambda x: x.rolling(20).mean())
    df['trend_dev'] = abs(df[PRICE_COL] - df['sma20']) / df['sma20']
    
    # DURGUNLUK TANIMI: Düşük Volatilite (<2.5) VE Düşük Trend Sapması (<%1.5)
    df['is_stagnant'] = (df['natr'] < 2.5) & (df['trend_dev'] < 0.015)
    
    # Son 3 günün kaçı durgun?
    df['stagnant_count_3d'] = df.groupby(SYMBOL_COL)['is_stagnant'].transform(lambda x: x.rolling(3).sum())
    
    # --- RS ZAYIFLIK HESABI ---
    # Son 5 günde %2'den fazla düşüş
    df['pct_change_5d'] = df.groupby(SYMBOL_COL)[PRICE_COL].transform(lambda x: x.pct_change(5))
    df['is_rs_weak'] = df['pct_change_5d'] < -0.02
    
    # Temizlik
    df.drop(['tr0', 'tr1', 'tr2', 'tr', 'atr', 'sma20', 'trend_dev', 'is_stagnant'], axis=1, inplace=True)
    return df

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)
    
    print(">> Loading Data & Model...")
    model, meta = load_model_and_meta()
    scaler = meta["sector_scaler"]
    features = meta["features"]
    
    # Veriyi Yükle
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    
    # *** KRİTİK: İndikatörleri Hesapla ***
    df = calculate_stagnation_indicators(df)
    
    # Feature Prep
    X = df[features].replace([np.inf, -np.inf], np.nan).fillna(df[features].median())
    Xs = scaler.transform(X, df[SECTOR_COL])
    df["score"] = model.predict_proba(Xs)[:, 1]
    
    # Test Set
    test = df[df["dataset_split"] == "test"].copy()
    test = test.sort_values(DATE_COL).reset_index(drop=True)
    test_grouped = test.groupby(DATE_COL)
    dates = sorted(test[DATE_COL].unique())
    date_to_index = {d: i for i, d in enumerate(dates)}
    
    # Portföy
    cash = INITIAL_CAPITAL
    portfolio = [] 
    equity_curve = []
    trade_log = []
    
    print(f">> Starting BACKTEST on {len(dates)} days...")
    
    for dt in dates:
        try:
            today_data = test_grouped.get_group(dt).set_index(SYMBOL_COL)
        except KeyError: continue
            
        idx = date_to_index[dt]
        next_dt = dates[idx + 1] if idx + 1 < len(dates) else None
        
        # 1) PLANLANMIŞ ÇIKIŞLAR
        for i in range(len(portfolio) - 1, -1, -1):
            pos = portfolio[i]
            if pos.get("exit_planned_date") == dt:
                sym = pos["symbol"]
                if sym not in today_data.index: continue
                
                raw_open = today_data.loc[sym][OPEN_COL]
                exit_price = raw_open * (1 - SLIPPAGE_SELL)
                
                revenue = pos["shares"] * exit_price
                commission = revenue * COMMISSION
                cash += (revenue - commission)
                
                trade_return = (exit_price / pos["entry_price"]) - 1
                trade_log.append({
                    "exit_date": dt, "symbol": sym,
                    "entry_date": pos["entry_date"],
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_price,
                    "return": trade_return,
                    "reason": pos.get("exit_reason_planned", "PLANNED"),
                    "days_held": pos["days_held"]
                })
                portfolio.pop(i)
                
        # 2) STOP-LOSS (Gün İçi)
        for i in range(len(portfolio) - 1, -1, -1):
            pos = portfolio[i]
            sym = pos["symbol"]
            if sym not in today_data.index:
                pos["days_held"] += 1
                continue
                
            row = today_data.loc[sym]
            low = row[LOW_COL]
            open_p = row[OPEN_COL]
            entry = pos["entry_price"]
            stop_level = entry * (1 + STOP_LOSS)
            
            if low <= stop_level:
                exit_price = open_p if open_p <= stop_level else stop_level
                revenue = pos["shares"] * exit_price
                commission = revenue * COMMISSION
                cash += (revenue - commission)
                
                trade_log.append({
                    "exit_date": dt, "symbol": sym,
                    "entry_date": pos["entry_date"],
                    "entry_price": entry, "exit_price": exit_price,
                    "return": (exit_price/entry)-1,
                    "reason": "STOP_LOSS", "days_held": pos["days_held"]
                })
                portfolio.pop(i)
            else:
                pos["days_held"] += 1
                
        # 3) ÇIKIŞ PLANLAMA (Smart Logic)
        today_sorted = today_data.sort_values("score", ascending=False)
        top_symbols = list(today_sorted.head(TOP_K).index)
        
        for pos in portfolio:
            if pos.get("exit_planned_date") is not None: continue
            
            sym = pos["symbol"]
            if next_dt is None or sym not in today_data.index: continue
            
            row = today_data.loc[sym]
            entry = pos["entry_price"]
            days = pos["days_held"]
            close = row[PRICE_COL]
            ret_close = (close / entry) - 1
            
            # --- A) PERF FAIL (GEVŞETİLMİŞ) ---
            # 8. Günde hala -%2'den daha zarardaysa ve top listede değilse sat
            if days >= 8 and ret_close < -0.02:
                if sym not in top_symbols:
                    pos["exit_planned_date"] = next_dt
                    pos["exit_reason_planned"] = "PERF_FAIL_RELAXED"
                    continue
                    
            # --- B) STAGNATION EXIT (GEVŞETİLMİŞ) ---
            # 10 günden fazla tutuyoruz, son 3 günü tamamen durgun ve kâr %3'ün altındaysa
            if days > 10 and row.get('stagnant_count_3d', 0) >= 3 and ret_close < 0.03:
                pos["exit_planned_date"] = next_dt
                pos["exit_reason_planned"] = "STAGNATION_EXIT"
                continue
                
            # --- C) RS ZAYIFLIK ---
            # 5 günden fazla tutuyoruz ve hisse sert düşüşte
            if days > 5 and row.get('is_rs_weak', False):
                if sym not in top_symbols:
                    pos["exit_planned_date"] = next_dt
                    pos["exit_reason_planned"] = "WEAK_RS_EXIT"
                    continue
            
            # --- D) STANDARD ---
            if days >= HORIZON:
                pos["exit_planned_date"] = next_dt
                pos["exit_reason_planned"] = "TIME_EXIT"
                continue
                
            if (ret_close >= TAKE_PROFIT) and (sym not in top_symbols):
                pos["exit_planned_date"] = next_dt
                pos["exit_reason_planned"] = "MODEL_TP"
                continue
                
        # 4) YENİ GİRİŞLER
        free_slots = MAX_POSITIONS - len(portfolio)
        if free_slots > 0 and next_dt is not None:
            candidates = today_sorted.head(TOP_K)
            try: next_day_data = test_grouped.get_group(next_dt).set_index(SYMBOL_COL)
            except KeyError: next_day_data = None
            
            for sym, row in candidates.iterrows():
                if free_slots <= 0: break
                if any(p["symbol"] == sym for p in portfolio): continue
                if next_day_data is None or sym not in next_day_data.index: continue
                
                raw_open = next_day_data.loc[sym][OPEN_COL]
                entry_price = raw_open * (1 + SLIPPAGE_BUY)
                shares = int((cash / free_slots) / entry_price)
                
                if shares > 0:
                    cost = shares * entry_price * (1 + COMMISSION)
                    if cash >= cost:
                        cash -= cost
                        portfolio.append({
                            "symbol": sym, "entry_price": entry_price, "shares": shares,
                            "entry_date": next_dt, "days_held": 0,
                            "exit_planned_date": None, "exit_reason_planned": None
                        })
                        free_slots -= 1
                        
        # 5) EQUITY
        port_val = sum(p["shares"] * (today_data.loc[p["symbol"]][PRICE_COL] if p["symbol"] in today_data.index else p["entry_price"]) for p in portfolio)
        equity_curve.append({"date": dt, "equity": cash + port_val})

    # RAPOR
    bt = pd.DataFrame(equity_curve)
    tr = pd.DataFrame(trade_log)
    final = bt["equity"].iloc[-1]
    
    print("\n===== FINAL OPTIMIZED BACKTEST =====")
    print(f"Final Equity: {final:,.2f}")
    print(f"Total Return: {(final/INITIAL_CAPITAL - 1):.2%}")
    if not tr.empty:
        print("Exit Reasons:")
        print(tr["reason"].value_counts())
    
    bt.to_csv(os.path.join(BACKTEST_DIR, "final_equity.csv"), index=False)
    tr.to_csv(os.path.join(BACKTEST_DIR, "final_trades.csv"), index=False)
    
    plt.figure(figsize=(10,6))
    plt.plot(bt["date"], bt["equity"])
    plt.title("Optimized Equity Curve")
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(BACKTEST_DIR, "final_equity_plot.png"))
    plt.close()

if __name__ == "__main__":
    main()