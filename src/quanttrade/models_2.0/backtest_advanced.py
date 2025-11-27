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

# ===== CONFIG =====
DATA_PATH   = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_realistic"

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
def calculate_stagnation_indicators(df):
    """
    Backtest öncesi veriye Durgunluk (ADX/ATR mantığı) ve RS Zayıflık
    sinyallerini işler.
    """
    print(">> Calculating Technical Indicators (Stagnation & RS)...")
    
    # Hesaplamaların doğru olması için tarih sıralı olmalı
    df = df.sort_values([SYMBOL_COL, DATE_COL])
    
    # --- A) DURGUNLUK (STAGNATION) HESABI ---
    # Gerçek ADX formülü karmaşıktır. Burada "Low Volatility + Flat Trend" mantığını kullanacağız.
    # 1. ATR (Average True Range)
    df['tr0'] = abs(df[HIGH_COL] - df[LOW_COL])
    df['tr1'] = abs(df[HIGH_COL] - df[PRICE_COL].shift(1))
    df['tr2'] = abs(df[LOW_COL] - df[PRICE_COL].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    
    # 14 günlük ATR
    df['atr'] = df.groupby(SYMBOL_COL)['tr'].transform(lambda x: x.rolling(14).mean())
    
    # Normalized ATR (NATR): Volatiliteyi yüzdesel yapar (%2, %5 gibi)
    # NATR < 2.0 ise hisse çok sıkışmış demektir.
    df['natr'] = (df['atr'] / df[PRICE_COL]) * 100
    
    # Trend Strength: Fiyatın 20 günlük ortalamadan ne kadar saptığı
    df['sma20'] = df.groupby(SYMBOL_COL)[PRICE_COL].transform(lambda x: x.rolling(20).mean())
    df['trend_dev'] = abs(df[PRICE_COL] - df['sma20']) / df['sma20']
    
    # KURAL: Eğer Volatilite düşükse (NATR < 2.5) VE Trend zayıfsa (%1.5'tan az sapma) -> DURGUN
    df['is_stagnant'] = (df['natr'] < 2.5) & (df['trend_dev'] < 0.015)
    
    # 3 Gün üst üste durgun mu? (Rolling sum 3 ise, son 3 gün True demektir)
    df['stagnant_3d_count'] = df.groupby(SYMBOL_COL)['is_stagnant'].transform(lambda x: x.rolling(3).sum())
    
    # --- B) RELATIVE STRENGTH (RS) ZAYIFLIK HESABI ---
    # Basitçe: Son 5 günde hisse %2'den fazla düştü mü?
    # (Piyasa verisi olmadığı için hissenin kendi momentumuna bakıyoruz)
    df['pct_change_5d'] = df.groupby(SYMBOL_COL)[PRICE_COL].transform(lambda x: x.pct_change(5))
    df['is_rs_weak'] = df['pct_change_5d'] < -0.02
    
    # Geçici kolonları temizle
    df.drop(['tr0', 'tr1', 'tr2', 'tr', 'atr', 'sma20', 'trend_dev'], axis=1, inplace=True)
    
    return df

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    print(">> Loading Data & Model...")
    model, meta = load_model_and_meta()
    scaler: SectorStandardScaler = meta["sector_scaler"]
    features = meta["features"]

    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    df = calculate_stagnation_indicators(df)

    # === Feature Prep ===
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

                raw_open = today_data.loc[sym][OPEN_COL]
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
        # 2) STOP-LOSS KONTROLÜ (GÜN İÇİ, GERÇEK SL SİMÜLASYONU)
        # ==========================
        for i in range(len(portfolio) - 1, -1, -1):
            pos = portfolio[i]
            sym = pos["symbol"]

            if sym not in today_data.index:
                pos["days_held"] += 1
                continue

            row = today_data.loc[sym]
            low = row[LOW_COL]
            open_price = row[OPEN_COL]
            close = row[PRICE_COL]
            entry = pos["entry_price"]

            stop_level = entry * (1 + STOP_LOSS)

            exit_reason = None
            exit_price = None

            if low <= stop_level:
                exit_reason = "STOP_LOSS"
                # Gap down senaryosu – burada slipajı ayrıca uygulamıyoruz,
                # zaten stop_level / open senaryosu yeterince konservatif.
                if open_price <= stop_level:
                    exit_price = open_price
                else:
                    exit_price = stop_level

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
        # ==========================
        # 3) MODEL + TP / TIME EXIT SCHEDULING (GÜNCELLENDİ)
        # ==========================
        today_sorted = today_data.sort_values("score", ascending=False)
        top_symbols = list(today_sorted.head(TOP_K).index)

        for pos in portfolio:
            # Zaten çıkış planlanmışsa geç
            if pos.get("exit_planned_date") is not None:
                continue

            sym = pos["symbol"]
            
            # Veri kontrolü
            if next_dt is None or sym not in today_data.index:
                continue

            row = today_data.loc[sym]
            entry = pos["entry_price"]
            days = pos["days_held"]
            close = row[PRICE_COL]
            
            # Anlık getiri
            ret_close = (close / entry) - 1

            # --- A) Performance Fail (İspat Fazı) ---
            # 5. günde hala kâr yoksa (maliyetin altındaysa veya nötrse) -> SAT
            if days >= 8 and ret_close < -0.02:
                # Ancak hisse modelin TOP listesinde hala varsa satma, şans ver.
                if sym not in top_symbols:
                    pos["exit_planned_date"] = next_dt
                    pos["exit_reason_planned"] = "PERF_FAIL_RELAXED"
                    continue

            # --- B) Stagnation Exit (Durgunluk) ---
            # İndikatör fonksiyonumuzda hesapladığımız 'stagnant_3d_count' kolonunu kullanıyoruz
            # Eğer değer 3 ise, son 3 gündür hisse ölü demektir.
            stagnant_days = row.get('stagnant_3d_count', 0) # (Bunu istersen 5 günlük hesaplatabilirsin ama şimdilik 3 kalsın)
            
            # Eğer 3 gündür durgunsa VE elde tutma süresi 10 günü geçtiyse VE kar %3'ün altındaysa
            if days > 10 and stagnant_days >= 3 and ret_close < 0.03:
                pos["exit_planned_date"] = next_dt
                pos["exit_reason_planned"] = "STAGNATION_EXIT_RELAXED"
                continue

            # --- C) Relative Weakness (Zayıflık) ---
            # Son 5 günde %2'den fazla düşmüşse ve elimizde 3 günden fazla tuttuysak
            if days > 5 and row.get('is_rs_weak', False):
                if sym not in top_symbols:
                    pos["exit_planned_date"] = next_dt
                    pos["exit_reason_planned"] = "WEAK_RS_EXIT"
                    continue

            # --- D) Standart Kurallar ---
            # Time Stop
            if days >= HORIZON:
                pos["exit_planned_date"] = next_dt
                pos["exit_reason_planned"] = "TIME_EXIT"
                continue

            # E) Model Take Profit
            if (ret_close >= TAKE_PROFIT) and (sym not in top_symbols):
                pos["exit_planned_date"] = next_dt
                pos["exit_reason_planned"] = "MODEL_TP"
                continue
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

                raw_open = next_day_data.loc[sym][OPEN_COL]
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
                curr_price = today_data.loc[sym][PRICE_COL]
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
