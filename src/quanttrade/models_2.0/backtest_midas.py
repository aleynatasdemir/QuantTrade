"""
REALISTIC SLOT-BASED BACKTESTER (T+1, MODEL+TP EXIT) + SLIPAJ
"""

import pandas as pd
import numpy as np
from datetime import timedelta
import joblib
from catboost import CatBoostClassifier
import glob, os
import matplotlib.pyplot as plt

from train_model import SectorStandardScaler  # sadece scaler kullanıyoruz

# KAP kategorileri (train ile aynı sırada)
KAP_CATEGORIES = ["FINANSAL_RAPOR", "GENEL_BILGI", "ILISKILI_TARAF", "SERMAYE_TEMETTU", "UNKNOWN", "YATIRIM_SOZLESME"]

# ===== CONFIG =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "master", "master_df.csv")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "model_results_alpha_20d")
BACKTEST_DIR = os.path.join(SCRIPT_DIR, "backtest_results_realistic")

HORIZON      = 20        # Maksimum tutma süresi (gün)
STOP_LOSS    = -0.05     # -%5
TAKE_PROFIT  = 0.10      # +%10
MAX_POSITIONS = 5        # Aynı anda max 5 hisse
INITIAL_CAPITAL = 100_000
COMMISSION   = 0.002     # Binde 2 (al + sat için her işlemde uygulanacak)

# >>> SLIPAJ <<<
SLIPPAGE_BUY  = 0.01   # %1
SLIPPAGE_SELL = 0.005  # %0.5 (satışta biraz daha iyi olursun genelde)


# Kolonlar
PRICE_COL  = "price_close"
OPEN_COL   = "price_open"
LOW_COL    = "price_low"
HIGH_COL   = "price_high"
DATE_COL   = "date"
SYMBOL_COL = "symbol"
SECTOR_COL = "sector"

TOP_K = 5  # modelin günlük en iyi K hissesi (sinyal seti)


def get_latest(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_model_and_meta():
    model_path = get_latest(os.path.join(RESULTS_DIR, "catboost_alpha20d_*.cbm"))
    meta_path  = get_latest(os.path.join(RESULTS_DIR, "neutralizer_alpha20d_*.pkl"))

    if not model_path or not meta_path:
        raise FileNotFoundError("Model dosyaları bulunamadı (catboost / meta).")

    model = CatBoostClassifier()
    model.load_model(model_path)

    meta = joblib.load(meta_path)
    return model, meta


def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    print(">> Loading Data & Model...")
    model, meta = load_model_and_meta()
    scaler: SectorStandardScaler = meta["sector_scaler"]
    features = meta["features"]

    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    # === Feature Prep ===
    # KAP one-hot encoding (train ile aynı)
    if "kap_category" in df.columns:
        for cat in KAP_CATEGORIES:
            col_name = f"kap_cat_{cat}"
            df[col_name] = (df["kap_category"] == cat).astype(int)
    
    # Eksik KAP kolonlarını 0 ile doldur (model bunları bekliyor)
    kap_numeric_cols = ["kap_sentiment", "kap_volatility", "kap_is_related_party", "kap_currency_impact"]
    kap_cat_cols = [f"kap_cat_{cat}" for cat in KAP_CATEGORIES]
    all_kap_cols = kap_numeric_cols + kap_cat_cols
    
    for col in all_kap_cols:
        if col not in df.columns:
            df[col] = 0
    
    X = df[features].replace([np.inf, -np.inf], np.nan).fillna(df[features].median())
    Xs = scaler.transform(X, df[SECTOR_COL])  # sadece sektör scaler
    df["score"] = model.predict_proba(Xs)[:, 1]

    # === Test Set ===
    test = df[df["dataset_split"] == "test"].copy()
    test = test.sort_values(DATE_COL).reset_index(drop=True)

    test_grouped = test.groupby(DATE_COL)
    dates = sorted(test[DATE_COL].unique())
    date_to_index = {d: i for i, d in enumerate(dates)}

    # === Portföy Durumu ===
    cash = INITIAL_CAPITAL
    portfolio = []  # aktif pozisyon listesi
    # {
    #   'symbol', 'entry_price', 'shares',
    #   'entry_date', 'days_held',
    #   'exit_planned_date', 'exit_reason_planned'
    # }

    equity_curve = []
    trade_log = []

    print(f">> Starting BACKTEST on {len(dates)} days (T+1, Model+TP Exit, Slippage)...")

    for dt in dates:
        # Günlük veri
        try:
            today_data = test_grouped.get_group(dt).set_index(SYMBOL_COL)
        except KeyError:
            continue

        # Bugünün indexi / yarın (next_dt)
        idx = date_to_index[dt]
        next_dt = dates[idx + 1] if idx + 1 < len(dates) else None

        # ==========================
        # 1) PLANLANMIŞ ÇIKIŞLAR (T+1 EXIT, MODEL TP / TIME EXIT)
        # ==========================
        for i in range(len(portfolio) - 1, -1, -1):
            pos = portfolio[i]
            if pos.get("exit_planned_date") == dt:
                sym = pos["symbol"]
                if sym not in today_data.index:
                    # Hisse bugün işlem görmüyorsa, exit'i ertele
                    continue

                exit_row = today_data.loc[sym]
                if isinstance(exit_row, pd.DataFrame):
                    exit_row = exit_row.iloc[0]
                raw_open = exit_row[OPEN_COL]
                # Satışta slipaj: açılıştan biraz daha kötü fiyat
                exit_price = raw_open * (1 - SLIPPAGE_SELL)

                revenue = pos["shares"] * exit_price
                commission = revenue * COMMISSION
                net_rev = revenue - commission
                cash += net_rev

                trade_return = (exit_price / pos["entry_price"]) - 1

                trade_log.append({
                    "exit_date": dt,
                    "symbol": sym,
                    "entry_date": pos["entry_date"],
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_price,
                    "return": trade_return,
                    "reason": pos.get("exit_reason_planned", "PLANNED_EXIT"),
                    "days_held": pos["days_held"]
                })

                portfolio.pop(i)

        # ==========================
        # 2) STOP-LOSS & TAKE-PROFIT KONTROLÜ (GÜN İÇİ)
        # ==========================
        for i in range(len(portfolio) - 1, -1, -1):
            pos = portfolio[i]
            sym = pos["symbol"]

            if sym not in today_data.index:
                pos["days_held"] += 1
                continue

            row = today_data.loc[sym]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            low = row[LOW_COL]
            high = row[HIGH_COL]
            open_price = row[OPEN_COL]
            close = row[PRICE_COL]
            entry = pos["entry_price"]

            stop_level = entry * (1 + STOP_LOSS)
            tp_level = entry * (1 + TAKE_PROFIT)

            exit_reason = None
            exit_price = None

            # Önce stop-loss kontrol (daha kötü senaryo öncelikli)
            if low <= stop_level:
                exit_reason = "STOP_LOSS"
                if open_price <= stop_level:
                    exit_price = open_price
                else:
                    exit_price = stop_level
            # Take-profit kontrol (high %10'a ulaştıysa)
            elif high >= tp_level:
                exit_reason = "TAKE_PROFIT"
                if open_price >= tp_level:
                    # Gap up senaryosu - açılıştan sat
                    exit_price = open_price
                else:
                    # Gün içinde TP seviyesine ulaştı
                    exit_price = tp_level

            if exit_reason is not None:
                revenue = pos["shares"] * exit_price
                commission = revenue * COMMISSION
                net_rev = revenue - commission
                cash += net_rev

                trade_return = (exit_price / entry) - 1

                trade_log.append({
                    "exit_date": dt,
                    "symbol": sym,
                    "entry_date": pos["entry_date"],
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "return": trade_return,
                    "reason": exit_reason,
                    "days_held": pos["days_held"]
                })

                portfolio.pop(i)
            else:
                pos["days_held"] += 1

        # ==========================
        # 3) MODEL + TP / TIME EXIT SCHEDULING (AKŞAM KONTROL → T+1 ÇIKIŞ)
        # ==========================
        today_sorted = today_data.sort_values("score", ascending=False)
        top_symbols = list(today_sorted.head(TOP_K).index)

        for pos in portfolio:
            if pos.get("exit_planned_date") is not None:
                continue

            if sym := pos["symbol"]:
                if next_dt is None:
                    continue

                if pos["days_held"] >= HORIZON:
                    pos["exit_planned_date"] = next_dt
                    pos["exit_reason_planned"] = "TIME_EXIT"
                    continue

                if sym in today_data.index:
                    tp_row = today_data.loc[sym]
                    if isinstance(tp_row, pd.DataFrame):
                        tp_row = tp_row.iloc[0]
                    close = tp_row[PRICE_COL]
                    entry = pos["entry_price"]
                    ret_close = (close / entry) - 1

                    if (ret_close >= TAKE_PROFIT) and (sym not in top_symbols):
                        pos["exit_planned_date"] = next_dt
                        pos["exit_reason_planned"] = "MODEL_TP"

        # ==========================
        # 4) YENİ GİRİŞLER (ENTRY, T+1 AÇILIŞTAN)
        # ==========================
        free_slots = MAX_POSITIONS - len(portfolio)

        if free_slots > 0 and next_dt is not None:
            candidates = today_sorted.head(TOP_K)

            try:
                next_day_data = test_grouped.get_group(next_dt).set_index(SYMBOL_COL)
            except KeyError:
                next_day_data = None

            for sym, row in candidates.iterrows():
                if free_slots <= 0:
                    break

                if any(p["symbol"] == sym for p in portfolio):
                    continue

                if next_day_data is None or sym not in next_day_data.index:
                    continue

                next_row = next_day_data.loc[sym]
                if isinstance(next_row, pd.DataFrame):
                    next_row = next_row.iloc[0]
                raw_open = next_row[OPEN_COL]
                # Alışta slipaj: açılıştan biraz daha kötü
                entry_price = raw_open * (1 + SLIPPAGE_BUY)

                capital_per_trade = cash / free_slots
                shares = int(capital_per_trade / entry_price)

                if shares <= 0:
                    continue

                cost = shares * entry_price
                commission = cost * COMMISSION
                total_cost = cost + commission

                if cash >= total_cost:
                    cash -= total_cost
                    portfolio.append({
                        "symbol": sym,
                        "entry_price": entry_price,
                        "shares": shares,
                        "entry_date": next_dt,
                        "days_held": 0,
                        "exit_planned_date": None,
                        "exit_reason_planned": None
                    })
                    free_slots -= 1

        # ==========================
        # 5) GÜNLÜK EQUITY HESABI (MARK-TO-MARKET)
        # ==========================
        portfolio_value = 0.0
        for pos in portfolio:
            sym = pos["symbol"]
            if sym in today_data.index:
                eq_row = today_data.loc[sym]
                if isinstance(eq_row, pd.DataFrame):
                    eq_row = eq_row.iloc[0]
                curr_price = eq_row[PRICE_COL]
            else:
                curr_price = pos["entry_price"]
            portfolio_value += pos["shares"] * curr_price

        total_equity = cash + portfolio_value
        equity_curve.append({"date": dt, "equity": total_equity})

    # 6) RAPORLAMA
    bt = pd.DataFrame(equity_curve)
    tr = pd.DataFrame(trade_log)

    initial = INITIAL_CAPITAL
    final = bt["equity"].iloc[-1]
    total_return = final / initial - 1

    daily_ret = bt["equity"].pct_change().dropna()
    if len(daily_ret) > 1:
        mu = daily_ret.mean()
        sigma = daily_ret.std() + 1e-12
        sharpe_daily = mu / sigma
        sharpe_annual = sharpe_daily * np.sqrt(252)
    else:
        sharpe_annual = np.nan

    cagr = (final / initial) ** (252 / len(bt)) - 1 if len(bt) > 0 else np.nan

    print("\n===== SLOT-BASED REALISTIC BACKTEST (T+1, MODEL+TP, SLIPPAGE) =====")
    print(f"Initial: {initial:,.2f} | Final: {final:,.2f}")
    print(f"Total Return: {total_return:.2%}")
    print(f"CAGR: {cagr:.2%}")
    print(f"Annual Sharpe: {sharpe_annual:.2f}")
    print(f"Total Trades: {len(tr)}")

    if not tr.empty:
        print(f"Win Rate: {(tr['return'] > 0).mean():.2%}")
        print("Exit reasons:")
        print(tr["reason"].value_counts())

    bt.to_csv(os.path.join(BACKTEST_DIR, "realistic_slot_bt_T1_modelTP_slip.csv"), index=False)
    tr.to_csv(os.path.join(BACKTEST_DIR, "realistic_slot_trades_T1_modelTP_slip.csv"), index=False)

    plt.figure(figsize=(10, 6))
    plt.plot(bt["date"], bt["equity"], label="Portfolio Equity")
    plt.title(
        f"Realistic Equity (Max {MAX_POSITIONS} Slots, H={HORIZON}, T+1, Model+TP, Slippage)"
    )
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(BACKTEST_DIR, "realistic_slot_equity_T1_modelTP_slip.png"))
    plt.close()


if __name__ == "__main__":
    main()
