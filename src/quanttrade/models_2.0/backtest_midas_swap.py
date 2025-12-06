"""
REALISTIC SLOT-BASED BACKTESTER (T+1, MODEL+TP EXIT, SLIPPAGE) + SCORE ROTATION
Bu versiyon:
- Zayıflayan hisseyi (Score < 0.50), güçlü aday varsa (Score > 0.80) acımasızca satar.
- Slotları sürekli "En Formda" hisselerle dolu tutmaya çalışır.
"""

import pandas as pd
import numpy as np
from datetime import timedelta
import joblib
from catboost import CatBoostClassifier
import glob, os
import matplotlib.pyplot as plt

from train_model import SectorStandardScaler

# ===== CONFIG =====
DATA_PATH   = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_realistic"

HORIZON      = 20        # Maksimum tutma süresi
STOP_LOSS    = -0.05     # -%5
TAKE_PROFIT  = 0.10      # +%10 (Model onayıyla)
MAX_POSITIONS = 5        # Slot Sayısı
INITIAL_CAPITAL = 100_000
COMMISSION   = 0.002     # Binde 2

# SLIPAJ (Gerçekçilik)
SLIPPAGE_BUY  = 0.01   # %1
SLIPPAGE_SELL = 0.005  # %0.5

# ROTATION AYARLARI (YENİ) 🔄
ROTATION_EXIT_THRESHOLD  = 0.50  # Elimdeki hissenin skoru buna düşerse tehlike
ROTATION_ENTRY_THRESHOLD = 0.80  # Dışarıda bundan yüksek skorlu varsa değişim yap

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

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)
    print(">> Loading Data & Model...")
    model, meta = load_model_and_meta()
    scaler = meta["sector_scaler"]
    features = meta["features"]

    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    # Feature Prep
    X = df[features].replace([np.inf, -np.inf], np.nan).fillna(df[features].median())
    Xs = scaler.transform(X, df[SECTOR_COL])
    df["score"] = model.predict_proba(Xs)[:, 1]

    test = df[df["dataset_split"] == "test"].copy()
    test = test.sort_values(DATE_COL).reset_index(drop=True)
    test_grouped = test.groupby(DATE_COL)
    dates = sorted(test[DATE_COL].unique())
    date_to_index = {d: i for i, d in enumerate(dates)}

    cash = INITIAL_CAPITAL
    portfolio = [] 
    equity_curve = []
    trade_log = []

    print(f">> Starting ROTATION BACKTEST on {len(dates)} days...")

    for dt in dates:
        try:
            today_data = test_grouped.get_group(dt).set_index(SYMBOL_COL)
        except KeyError: continue

        idx = date_to_index[dt]
        next_dt = dates[idx + 1] if idx + 1 < len(dates) else None

        # -------------------------------------------------
        # 1) PLANLANMIŞ ÇIKIŞLAR (T+1 Sabah)
        # -------------------------------------------------
        for i in range(len(portfolio) - 1, -1, -1):
            pos = portfolio[i]
            if pos.get("exit_planned_date") == dt:
                sym = pos["symbol"]
                if sym not in today_data.index: continue

                raw_open = today_data.loc[sym][OPEN_COL]
                exit_price = raw_open * (1 - SLIPPAGE_SELL)

                revenue = pos["shares"] * exit_price
                net_rev = revenue * (1 - COMMISSION)
                cash += net_rev

                trade_return = (exit_price / pos["entry_price"]) - 1
                trade_log.append({
                    "exit_date": dt, "symbol": sym, "entry_date": pos["entry_date"],
                    "entry_price": pos["entry_price"], "exit_price": exit_price,
                    "return": trade_return, "reason": pos.get("exit_reason_planned", "PLANNED"),
                    "days_held": pos["days_held"]
                })
                portfolio.pop(i)

        # -------------------------------------------------
        # 2) STOP-LOSS KONTROLÜ (Gün İçi)
        # -------------------------------------------------
        for i in range(len(portfolio) - 1, -1, -1):
            pos = portfolio[i]
            sym = pos["symbol"]
            if sym not in today_data.index:
                pos["days_held"] += 1
                continue

            row = today_data.loc[sym]
            stop_level = pos["entry_price"] * (1 + STOP_LOSS)
            
            exit_reason = None
            exit_price = None

            if row[LOW_COL] <= stop_level:
                exit_reason = "STOP_LOSS"
                # Gap kontrolü
                exit_price = row[OPEN_COL] if row[OPEN_COL] <= stop_level else stop_level

            if exit_reason:
                revenue = pos["shares"] * exit_price
                net_rev = revenue * (1 - COMMISSION)
                cash += net_rev
                
                trade_return = (exit_price / pos["entry_price"]) - 1
                trade_log.append({
                    "exit_date": dt, "symbol": sym, "entry_date": pos["entry_date"],
                    "entry_price": pos["entry_price"], "exit_price": exit_price,
                    "return": trade_return, "reason": exit_reason,
                    "days_held": pos["days_held"]
                })
                portfolio.pop(i)
            else:
                pos["days_held"] += 1

        # -------------------------------------------------
        # 3) ANALİZ & KARAR (ROTASYON DAHİL)
        # -------------------------------------------------
        if next_dt is not None:
            today_sorted = today_data.sort_values("score", ascending=False)
            top_symbols = list(today_sorted.head(TOP_K).index)
            
            # Dışarıdaki (Portföyde olmayan) en iyi adayı bul
            current_holdings = [p['symbol'] for p in portfolio]
            candidates_outside = today_data[~today_data.index.isin(current_holdings)]
            
            best_outside_score = 0
            if not candidates_outside.empty:
                best_outside_score = candidates_outside["score"].max()

            for pos in portfolio:
                if pos.get("exit_planned_date") is not None: continue
                
                sym = pos["symbol"]
                if sym not in today_data.index: continue
                
                current_score = today_data.loc[sym, "score"]
                
                # --- ÇIKIŞ SENARYOLARI ---
                
                # A) SÜRE DOLDU
                if pos["days_held"] >= HORIZON:
                    pos["exit_planned_date"] = next_dt
                    pos["exit_reason_planned"] = "TIME_EXIT"
                    continue
                
                # B) MODEL + TP (Kâr aldım ve model artık sevmiyor)
                close = today_data.loc[sym][PRICE_COL]
                ret_close = (close / pos["entry_price"]) - 1
                if (ret_close >= TAKE_PROFIT) and (sym not in top_symbols):
                    pos["exit_planned_date"] = next_dt
                    pos["exit_reason_planned"] = "MODEL_TP"
                    continue
                
                # C) ROTASYON (Zayıfı at, güçlüyü al) - YENİ EKLEME 🔄
                # Eğer elimdeki < 0.50 VE Dışarıda > 0.80 varsa
                if (current_score < ROTATION_EXIT_THRESHOLD) and \
                   (best_outside_score > ROTATION_ENTRY_THRESHOLD):
                    
                    pos["exit_planned_date"] = next_dt
                    pos["exit_reason_planned"] = "SCORE_ROTATION"
                    # Not: Bu hisse yarın sabah satılacak, yer açılacak.
                    # Yeni alım da yarın sabah yapılacak.

        # -------------------------------------------------
        # 4) YENİ GİRİŞLER (ENTRY)
        # -------------------------------------------------
        # Not: Rotasyon ile "Yarın Satılacak" olanlar henüz portföyden düşmedi.
        # Slot kontrolü yaparken "exit_planned_date"i dolu olanları "Sanal Boşluk" saymalıyız
        # ki yarın sabah hem satıp hem yerine yenisini alabilelim.
        
        actual_holdings = len([p for p in portfolio if p.get("exit_planned_date") is None])
        free_slots = MAX_POSITIONS - actual_holdings

        if free_slots > 0 and next_dt is not None:
            candidates = today_sorted.head(TOP_K + 5) # Biraz geniş bak
            
            try:
                next_day_data = test_grouped.get_group(next_dt).set_index(SYMBOL_COL)
            except: next_day_data = None

            if next_day_data is not None:
                for sym, row in candidates.iterrows():
                    if free_slots <= 0: break
                    
                    # Zaten portföyde mi (ve yarın satılmıyor mu?)
                    # Eğer yarın satılacaksa, "zaten portföyde" sayma, çünkü satıp geri almayız (mantıksız)
                    # Ama aynı hisseyi satıp tekrar almak komisyon kaybı olur.
                    # Basit kural: Portföyde adı geçen hisseyi alma.
                    if any(p["symbol"] == sym for p in portfolio):
                        continue

                    if sym not in next_day_data.index: continue

                    # ALIM EMRİ
                    raw_open = next_day_data.loc[sym][OPEN_COL]
                    entry_price = raw_open * (1 + SLIPPAGE_BUY)
                    
                    # Sermaye hesabı (Basitçe kalan nakiti değil, toplam portföy / slot hedefi gibi düşünelim)
                    # Şimdilik basit: (Nakit + Yarın gelecek nakit) / Boş Slot
                    # Ama yarın gelecek nakiti bilmediğimiz için mevcudu kullanıyoruz.
                    capital_per_trade = cash / max(1, free_slots)
                    
                    shares = int(capital_per_trade / entry_price)
                    if shares > 0:
                        cost = shares * entry_price
                        total_cost = cost * (1 + COMMISSION)
                        
                        if cash >= total_cost:
                            cash -= total_cost
                            portfolio.append({
                                "symbol": sym, "entry_price": entry_price, "shares": shares,
                                "entry_date": next_dt, "days_held": 0,
                                "exit_planned_date": None, "exit_reason_planned": None
                            })
                            free_slots -= 1

        # -------------------------------------------------
        # 5) EQUITY
        # -------------------------------------------------
        port_val = 0
        for pos in portfolio:
            sym = pos["symbol"]
            px = today_data.loc[sym][PRICE_COL] if sym in today_data.index else pos["entry_price"]
            port_val += pos["shares"] * px
        
        equity_curve.append({"date": dt, "equity": cash + port_val})

    # SONUÇLAR
    bt = pd.DataFrame(equity_curve)
    tr = pd.DataFrame(trade_log)
    final_eq = bt["equity"].iloc[-1]
    ret = final_eq / INITIAL_CAPITAL - 1
    
    print("\n===== ROTATION BACKTEST SONUÇLARI =====")
    print(f"Final: {final_eq:,.2f} TL | Getiri: %{ret*100:.2f}")
    print(f"Toplam İşlem: {len(tr)}")
    if not tr.empty:
        print("Çıkış Sebepleri:")
        print(tr["reason"].value_counts())

    bt.to_csv(os.path.join(BACKTEST_DIR, "rotation_bt.csv"), index=False)
    tr.to_csv(os.path.join(BACKTEST_DIR, "rotation_trades.csv"), index=False)
    
    plt.figure(figsize=(10,6))
    plt.plot(bt["date"], bt["equity"])
    plt.title("Backtest with SCORE ROTATION")
    plt.savefig(os.path.join(BACKTEST_DIR, "rotation_equity.png"))
    plt.close()

if __name__ == "__main__":
    main()