"""
LIVE PORTFOLIO MANAGER (T+1, MAX 5 POSITIONS, 5% SL)

Kullanım:
- Her akşam (borsa kapandıktan sonra) çalıştır.
- İlk çalıştırdığında:
    - Portföy boş, 100.000 TL nakit ile başlar.
    - Son güne göre YARIN için alım önerileri üretir (pending_buys).
- Sonraki çalıştırmalarda:
    - Bir önceki günün pending_buys'larını bugünün açılış fiyatıyla 'gerçekleştirir'
    - Mevcut pozisyonlara STOP / TIME EXIT uygular
    - Portföy değeri & getiriyi kaydeder
    - Bugüne göre YARIN için yeni alım önerileri üretir.

Stop-loss:
- Script, OHLC'ye bakarak "bugün low %5 altında gördüyse" stop olmuş varsayıyor.
- Gerçekte sen Midas'ta %5 SL emirlerini koyacaksın.
"""

import os
import json
import glob
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from catboost import CatBoostClassifier

from train_model import SectorStandardScaler  # sadece scaler gerekiyor

# ========================
# CONFIG
# ========================

# Project root'a göre paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))

DATA_PATH    = os.path.join(PROJECT_ROOT, "data", "master", "master_df.csv")
RESULTS_DIR  = "model_results_alpha_20d"

STATE_PATH   = "live_state_T1.json"
TRADES_CSV   = "live_trades_T1.csv"
EQUITY_CSV   = "live_equity_T1.csv"
EQUITY_PNG   = "live_equity_T1.png"

HORIZON_DAYS   = 20        # max tutma süresi
STOP_LOSS_PCT  = -0.05     # -%5
MAX_POSITIONS  = 5
INITIAL_CAPITAL = 15_000
COMMISSION     = 0.002     # binde 2

PRICE_COL   = "price_close"
OPEN_COL    = "price_open"
LOW_COL     = "price_low"
HIGH_COL    = "price_high"
DATE_COL    = "date"
SYMBOL_COL  = "symbol"
SECTOR_COL  = "sector"


# ========================
# HELPERS
# ========================

def get_latest(pattern: str):
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_model_and_meta():
    model_path = get_latest(os.path.join(RESULTS_DIR, "catboost_alpha20d_*.cbm"))
    meta_path  = get_latest(os.path.join(RESULTS_DIR, "neutralizer_alpha20d_*.pkl"))

    if model_path is None or meta_path is None:
        raise FileNotFoundError("Model veya meta dosyası bulunamadı.")

    model = CatBoostClassifier()
    model.load_model(model_path)

    meta = joblib.load(meta_path)
    # meta: { "sector_scaler": sec_scaler_final, "features": feature_names }
    return model, meta


def load_state():
    """Diskten portföy durumunu oku. Yoksa sıfırdan başlat."""
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r") as f:
            state = json.load(f)
    else:
        state = {
            "cash": INITIAL_CAPITAL,
            "positions": [],      # [{symbol, entry_price, shares, entry_date(str), days_held}]
            "pending_buys": [],   # [{symbol, planned_capital, decision_date(str)}]
            "last_date": None     # en son işlenen tarih (str)
        }
    return state


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def compute_stop_exit(entry_price, stop_pct, today_row):
    """
    Stop-loss tetiklenmiş mi?

    - Gap + intraday:
      * Eğer open stop seviyesinin altındaysa → gap'te stop
      * Eğer gün içi low stop seviyesinin altına inmişse → stop seviyesinden çık
    """
    stop_level = entry_price * (1.0 + stop_pct)

    today_open = today_row[OPEN_COL]
    today_low  = today_row[LOW_COL]

    # 1) Gap'te stop
    if today_open <= stop_level:
        exit_price = today_open
        reason = "STOP_LOSS"
        return True, exit_price, reason

    # 2) Gün içi low stop seviyesi altına inmişse
    if today_low <= stop_level:
        exit_price = stop_level
        reason = "STOP_LOSS"
        return True, exit_price, reason

    return False, None, None


# ========================
# MAIN
# ========================

def main():
    print(">> Loading model & state...")
    model, meta = load_model_and_meta()
    scaler: SectorStandardScaler = meta["sector_scaler"]
    feature_names = meta["features"]

    state = load_state()
    cash = float(state["cash"])
    positions = state["positions"]
    pending_buys = state["pending_buys"]
    last_date_str = state["last_date"]
    last_date = pd.to_datetime(last_date_str) if last_date_str is not None else None

    print(">> Loading data...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    # Model scoring
    X = df[feature_names].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(df[feature_names].median())
    sector = df[SECTOR_COL].fillna("other").astype(str)

    Xs = scaler.transform(X, sector)
    df["score"] = model.predict_proba(Xs)[:, 1]

    # Sadece BIST günlerini sırala
    dates = sorted(df[DATE_COL].unique())
    if not dates:
        print("Veri yok.")
        return

    grouped = df.groupby(DATE_COL)

    # Hangi tarihleri yeni işleyeceğiz?
    if last_date is None:
        new_dates = []  # ilk çalıştırma → geçmişi simüle etmiyoruz
        ref_date = dates[-1]  # sinyal üretilecek referans gün (bugün)
    else:
        new_dates = [d for d in dates if d > last_date]
        ref_date = new_dates[-1] if new_dates else last_date

    # ============================
    # 1) VARSA YENİ GÜNLERİ SİMÜLE ET
    # ============================
    equity_rows = []
    trade_rows = []

    prev_equity = cash  # pozisyon yoksa sadece nakit

    for current_date in new_dates:
        today = current_date
        today_data = grouped.get_group(today).set_index(SYMBOL_COL)

        # --- 1.a) Pending BUY emirlerini bugünün açılışında gerçekleştir ---
        if pending_buys:
            new_pending = []
            for order in pending_buys:
                sym = order["symbol"]
                planned_capital = float(order["planned_capital"])

                if sym not in today_data.index:
                    # ilgili hissede bugün veri yoksa emir havada kalsın
                    new_pending.append(order)
                    continue

                open_price = today_data.loc[sym, OPEN_COL]
                shares = int(planned_capital / open_price)
                if shares <= 0:
                    continue

                cost = shares * open_price
                comm = cost * COMMISSION
                total_cost = cost + comm

                if total_cost > cash:
                    # para yetmiyorsa bu emri de havada bırak
                    new_pending.append(order)
                    continue

                cash -= total_cost

                positions.append({
                    "symbol": sym,
                    "entry_price": float(open_price),
                    "shares": int(shares),
                    "entry_date": today.strftime("%Y-%m-%d"),
                    "days_held": 0
                })

                trade_rows.append({
                    "entry_date": today.strftime("%Y-%m-%d"),
                    "exit_date": "",
                    "symbol": sym,
                    "entry_price": float(open_price),
                    "exit_price": "",
                    "shares": int(shares),
                    "return": "",
                    "reason": "ENTRY",
                    "days_held": 0
                })

            pending_buys = new_pending

        # --- 1.b) MEVCUT POZİSYONLARA STOP/TIME EXIT UYGULA ---
        for i in range(len(positions) - 1, -1, -1):
            pos = positions[i]
            sym = pos["symbol"]

            if sym not in today_data.index:
                # veri yok, elde tutmaya devam
                pos["days_held"] += 1
                continue

            row = today_data.loc[sym]
            entry_price = float(pos["entry_price"])
            close_price = float(row[PRICE_COL])

            exit_flag, exit_price, reason = compute_stop_exit(
                entry_price, STOP_LOSS_PCT, row
            )

            # Time exit kontrolü (stop olmadıysa)
            if (not exit_flag) and (pos["days_held"] >= HORIZON_DAYS):
                exit_flag = True
                exit_price = close_price
                reason = "TIME_EXIT"

            if exit_flag:
                revenue = pos["shares"] * exit_price
                comm = revenue * COMMISSION
                net_revenue = revenue - comm
                cash += net_revenue

                trade_ret = (exit_price / entry_price) - 1.0

                trade_rows.append({
                    "entry_date": pos["entry_date"],
                    "exit_date": today.strftime("%Y-%m-%d"),
                    "symbol": sym,
                    "entry_price": entry_price,
                    "exit_price": float(exit_price),
                    "shares": int(pos["shares"]),
                    "return": float(trade_ret),
                    "reason": reason,
                    "days_held": int(pos["days_held"])
                })

                positions.pop(i)
            else:
                pos["days_held"] += 1

        # --- 1.c) GÜNLÜK EQUITY ---
        portfolio_value = 0.0
        for pos in positions:
            sym = pos["symbol"]
            if sym in today_data.index:
                px = float(today_data.loc[sym, PRICE_COL])
            else:
                px = float(pos["entry_price"])
            portfolio_value += pos["shares"] * px

        total_equity = cash + portfolio_value
        daily_ret = (total_equity / prev_equity) - 1.0 if prev_equity > 0 else 0.0
        prev_equity = total_equity

        equity_rows.append({
            "date": today.strftime("%Y-%m-%d"),
            "equity": float(total_equity),
            "cash": float(cash),
            "portfolio_value": float(portfolio_value),
            "daily_return": float(daily_ret),
            "n_positions": len(positions)
        })

        # Bu günü işledik
        state["last_date"] = today.strftime("%Y-%m-%d")

    # ============================
    # 2) REFERANS GÜN İÇİN YARININ ALIM ÖNERİLERİ
    # ============================

    ref_data = grouped.get_group(ref_date).set_index(SYMBOL_COL)

    # Halihazırda elde bulunan semboller
    current_syms = {p["symbol"] for p in positions}
    # Zaten pending'de olanlar
    pending_syms = {o["symbol"] for o in pending_buys}

    used_slots = len(current_syms.union(pending_syms))
    free_slots = max(0, MAX_POSITIONS - used_slots)

    new_signals = []
    if free_slots > 0:
        candidates = (
            ref_data
            .sort_values("score", ascending=False)
            .reset_index()
        )

        picks = []
        for _, row in candidates.iterrows():
            sym = row[SYMBOL_COL]
            if sym in current_syms:
                continue
            if sym in pending_syms:
                continue
            picks.append(row)
            if len(picks) >= free_slots:
                break

        if picks:
            capital_per_trade = cash / free_slots if free_slots > 0 else 0.0
            for row in picks:
                sym = row[SYMBOL_COL]
                pending_buys.append({
                    "symbol": sym,
                    "planned_capital": float(capital_per_trade),
                    "decision_date": ref_date.strftime("%Y-%m-%d")
                })
                new_signals.append({
                    "symbol": sym,
                    "score": float(row["score"]),
                    "planned_capital": float(capital_per_trade)
                })

    # ============================
    # 3) STATE + LOG DOSYALARINI KAYDET
    # ============================

    # Add current_price to each position for frontend
    ref_data_for_prices = grouped.get_group(ref_date).set_index(SYMBOL_COL) if ref_date in df[DATE_COL].values else None
    if ref_data_for_prices is not None:
        for pos in positions:
            sym = pos["symbol"]
            try:
                pos["current_price"] = float(ref_data_for_prices.loc[sym, PRICE_COL])
            except KeyError:
                pos["current_price"] = float(pos["entry_price"])  # Fallback to entry price
    
    state["cash"] = float(cash)
    state["positions"] = positions
    state["pending_buys"] = pending_buys
    if state["last_date"] is None:
        state["last_date"] = ref_date.strftime("%Y-%m-%d")

    save_state(state)

    # Equity log
    if equity_rows:
        eq_df_new = pd.DataFrame(equity_rows)
        if os.path.exists(EQUITY_CSV):
            eq_old = pd.read_csv(EQUITY_CSV)
            eq_df = pd.concat([eq_old, eq_df_new], ignore_index=True)
        else:
            eq_df = eq_df_new
        eq_df.to_csv(EQUITY_CSV, index=False)

        # Grafik
        plt.figure(figsize=(10, 5))
        plt.plot(pd.to_datetime(eq_df["date"]), eq_df["equity"])
        plt.title("LIVE Portfolio Equity (T+1, Max 5 Positions, 5% SL)")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(EQUITY_PNG)
        plt.close()

    # Trade log
    if trade_rows:
        tr_df_new = pd.DataFrame(trade_rows)
        if os.path.exists(TRADES_CSV):
            tr_old = pd.read_csv(TRADES_CSV)
            tr_df = pd.concat([tr_old, tr_df_new], ignore_index=True)
        else:
            tr_df = tr_df_new
        tr_df.to_csv(TRADES_CSV, index=False)

    # ============================
    # 4) KONSOLA ÖZET YAZ
    # ============================

    print("\n===== LIVE PORTFOLIO STATE (T+1) =====")
    print(f"Son işlenen tarih        : {state['last_date']}")
    print(f"Nakit                    : {cash:,.2f} TL")
    print(f"Aktif pozisyon sayısı    : {len(positions)}")

    if positions:
        print("\nAktif pozisyonlar:")
        ref_px = ref_data[PRICE_COL] if ref_date in df[DATE_COL].values else None
        for p in positions:
            sym = p["symbol"]
            entry = float(p["entry_price"])
            shares = int(p["shares"])
            days_held = int(p["days_held"])

            # Son fiyat olarak referans güne bak (aynı günse)
            try:
                last_px = float(ref_data.loc[sym, PRICE_COL])
            except KeyError:
                last_px = entry

            pnl_pct = (last_px / entry - 1.0) * 100.0
            pnl_tl = (last_px - entry) * shares

            print(
                f"  {sym}: {shares} adet, giriş {entry:.2f}, "
                f"son {last_px:.2f}, PnL {pnl_pct:.2f}% ({pnl_tl:,.0f} TL), "
                f"gün sayısı {days_held}"
            )
    else:
        print("\nAktif pozisyon yok.")

    if new_signals:
        print("\n=== YARIN İÇİN YENİ ALIM ÖNERİLERİ (T+1) ===")
        for s in new_signals:
            print(
                f"  {s['symbol']}: score={s['score']:.3f}, "
                f"tahmini sermaye ~ {s['planned_capital']:,.0f} TL"
            )
        print("\nNot: Bunlar yarın sabah açılışa 'piyasa' veya 'makul limit' ile alman gerekenler.")
    else:
        print("\nYarın için yeni alım önerisi yok (slot yok veya uygun aday yok).")


if __name__ == "__main__":
    main()
