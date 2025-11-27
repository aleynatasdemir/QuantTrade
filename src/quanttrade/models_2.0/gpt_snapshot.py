import os
import json
import pandas as pd
import numpy as np
from datetime import timedelta
import joblib
from catboost import CatBoostClassifier
from train_model import SectorStandardScaler

# ====================
# CONFIG
# ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
DATA_PATH     = os.path.join(PROJECT_ROOT, "data", "master", "master_df.csv")
STATE_PATH    = "live_state_T1.json"
TRADES_CSV    = "live_trades_T1.csv"
EQUITY_CSV    = "live_equity_T1.csv"
RESULTS_DIR   = "model_results_alpha_20d"
SNAPSHOT_PATH = "snapshot_latest.json"

# --- SİSTEM PARAMETRELERİ (GPT İÇİN) ---
SLIPPAGE_BUY    = 0.01      # %1.0
SLIPPAGE_SELL   = 0.005     # %0.5
COMMISSION      = 0.002     # %0.2
STOP_LOSS_PCT   = -0.05     # -%5
PATIENCE_DAYS   = 8         # Dokunulmazlık süresi
STAGNATION_DAYS = 10        # Durgunluk için bekleme süresi

TOP_K                = 10
N_PRICE_DAYS         = 20
N_RECENT_TRADES      = 15
N_EQUITY_DAYS        = 60

DATE_COL   = "date"
SYMBOL_COL = "symbol"
PRICE_COL  = "price_close"
OPEN_COL   = "price_open"
HIGH_COL   = "price_high"
LOW_COL    = "price_low"
SECTOR_COL = "sector"

# ====================
# LOAD MODEL IF EXISTS
# ====================
def load_model():
    model_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".cbm")]
    meta_files  = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".pkl")]

    if not model_files or not meta_files:
        return None, None

    model_path = os.path.join(RESULTS_DIR, sorted(model_files)[-1])
    meta_path  = os.path.join(RESULTS_DIR, sorted(meta_files)[-1])

    model = CatBoostClassifier()
    model.load_model(model_path)
    meta = joblib.load(meta_path)

    return model, meta


# ====================
# STAGNATION / RS
# ====================
def add_indicators(df):
    df = df.sort_values([SYMBOL_COL, DATE_COL])

    df["tr"] = df[[HIGH_COL, LOW_COL]].max(axis=1) - df[[HIGH_COL, LOW_COL]].min(axis=1)
    df["atr"] = df.groupby(SYMBOL_COL)["tr"].transform(lambda x: x.rolling(14).mean())
    df["natr"] = (df["atr"] / df[PRICE_COL]) * 100

    df["sma20"] = df.groupby(SYMBOL_COL)[PRICE_COL].transform(lambda x: x.rolling(20).mean())
    df["trend_dev"] = (df[PRICE_COL] - df["sma20"]).abs() / df["sma20"]

    df["is_stagnant"] = (df["natr"] < 2.5) & (df["trend_dev"] < 0.015)
    df["stagnant_3d"] = df.groupby(SYMBOL_COL)["is_stagnant"].transform(lambda x: x.rolling(3).sum())

    df["pct_change_5d"] = df.groupby(SYMBOL_COL)[PRICE_COL].transform(lambda x: x.pct_change(5))
    df["is_rs_weak"] = df["pct_change_5d"] < -0.02

    return df


# ====================
# MAIN
# ====================
def main():
    # --- Load live state ---
    if not os.path.exists(STATE_PATH):
        print(f"Hata: {STATE_PATH} bulunamadı. Önce live scripti çalıştırın.")
        return

    with open(STATE_PATH, "r") as f:
        state = json.load(f)

    cash      = float(state["cash"])
    positions = state["positions"]
    pending   = state["pending_buys"]
    
    # Tarih formatı kontrolü
    if state["last_date"]:
        last_date = pd.to_datetime(state["last_date"])
    else:
        # Eğer state yeni oluşturulduysa ve tarih yoksa bugünü al
        last_date = pd.Timestamp.now().normalize()

    # --- Load master data ---
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    
    # Geleceği görme (Lookahead) engelleme
    df = df[df[DATE_COL] <= last_date].copy()
    
    # İndikatörleri hesapla
    df = add_indicators(df)

    # --- Model score ---
    model, meta = load_model()
    if model:
        features = meta["features"]
        scaler   = meta["sector_scaler"]

        X  = df[features].fillna(df[features].median())
        sec = df[SECTOR_COL].fillna("other").astype(str)
        Xs = scaler.transform(X, sec)
        df["score"] = model.predict_proba(Xs)[:, 1]
    else:
        df["score"] = np.nan

    # --- Extract symbols (Portfolio + Pending) ---
    syms = set([p["symbol"] for p in positions] +
               [o["symbol"] for o in pending])

    # Price window (Son N gün)
    price_from = last_date - timedelta(days=N_PRICE_DAYS)
    prices_df = df[(df[DATE_COL] >= price_from) & (df[SYMBOL_COL].isin(syms))]

    # --- Model signals today (Top K) ---
    today_df = df[df[DATE_COL] == last_date].copy()
    today_df = today_df.sort_values("score", ascending=False)

    model_block = []
    for i, r in today_df.head(TOP_K).iterrows():
        model_block.append({
            "symbol": r[SYMBOL_COL],
            "score": float(r["score"]),
            "rank": int(i + 1)
        })

    # --- Portfolio positions extended ---
    portfolio_block = []
    for p in positions:
        entry = float(p["entry_price"])
        curr  = float(p.get("current_price", entry))
        ret_pct = (curr / entry - 1) * 100

        # Son günün indikatör durumunu bul
        sym_df = prices_df[prices_df[SYMBOL_COL] == p["symbol"]]
        if not sym_df.empty:
            last_row = sym_df.sort_values(DATE_COL).iloc[-1]
            stagn  = int(last_row.get("stagnant_3d", 0))
            weak   = bool(last_row.get("is_rs_weak", False))
        else:
            stagn = 0
            weak = False

        portfolio_block.append({
            "symbol": p["symbol"],
            "entry_price": entry,
            "current_price": curr,
            "shares": p["shares"],
            "days_held": p["days_held"],
            "return_pct": ret_pct,
            "stagnation_3d": stagn,
            "is_rs_weak": weak,
            "exit_planned": p.get("exit_planned", False),
            "exit_reason": p.get("exit_reason_planned")
        })

    # --- Pending buys ---
    pending_block = []
    for o in pending:
        pending_block.append({
            "symbol": o["symbol"],
            "planned_capital": float(o["planned_capital"]),
            "decision_date": o["decision_date"]
        })

    # --- Trades ---
    if os.path.exists(TRADES_CSV):
        trades_df = pd.read_csv(TRADES_CSV)
        trades_df = trades_df.tail(N_RECENT_TRADES)
        trades_block = []
        for _, r in trades_df.iterrows():
            trades_block.append({
                "symbol": r["symbol"],
                "entry": float(r["entry_price"]),
                "exit": float(r["exit_price"]) if pd.notnull(r["exit_price"]) else None,
                "return_pct": float(r["return"] * 100) if "return" in r else None,
                "reason": r.get("reason", None)
            })
    else:
        trades_block = []

    # --- Equity curve ---
    if os.path.exists(EQUITY_CSV):
        eq = pd.read_csv(EQUITY_CSV)
        eq[DATE_COL] = pd.to_datetime(eq[DATE_COL])
        eq = eq.tail(N_EQUITY_DAYS)
        eq_block = [{"date": d[DATE_COL].strftime("%Y-%m-%d"), "equity": float(d["equity"])} for _, d in eq.iterrows()]
    else:
        eq_block = []

    # -----------------------------------------
    # FINAL SNAPSHOT → GPT'YE GÖNDERECEĞİN JSON
    # -----------------------------------------
    snapshot = {
        "as_of": last_date.strftime("%Y-%m-%d"),
        
        # >>> YENİ EKLENEN KISIM: SİSTEM KURALLARI <<<
        "system_rules": {
            "slippage_buy_pct": SLIPPAGE_BUY * 100,      # %1.0 olarak görsün
            "slippage_sell_pct": SLIPPAGE_SELL * 100,    # %0.5
            "commission_pct": COMMISSION * 100,          # %0.2
            "stop_loss_pct": STOP_LOSS_PCT * 100,        # -%5.0
            "patience_days": PATIENCE_DAYS,              # 8 gün
            "stagnation_days": STAGNATION_DAYS,          # 10 gün
            "strategy_description": "T+1 Systematic Momentum with Stagnation Filter"
        },
        
        "portfolio": portfolio_block,
        "pending_buys": pending_block,
        "recent_trades": trades_block,
        "equity_curve": eq_block,
        "model_signals": model_block,
        "prices": [
            {
                "date": r[DATE_COL].strftime("%Y-%m-%d"),
                "symbol": r[SYMBOL_COL],
                "close": float(r[PRICE_COL]),
                "open": float(r[OPEN_COL]),
                "high": float(r[HIGH_COL]),
                "low": float(r[LOW_COL]),
                "natr": float(r.get("natr", np.nan)),
                "stagnant_3d": int(r.get("stagnant_3d", 0)),
                "is_rs_weak": bool(r.get("is_rs_weak", False)),
                "pct_change_5d": float(r.get("pct_change_5d", np.nan))
            }
            for _, r in prices_df.iterrows()
        ]
    }
    
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    
    # Konsola bas → GPT API'ye bunu vereceksin
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"\n>> Snapshot kaydedildi: {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()