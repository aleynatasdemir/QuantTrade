import pandas as pd
import sys
import os

# Add src to python path
sys.path.append(os.path.abspath('src'))
print(f"DEBUG: sys.path: {sys.path}")
print(f"DEBUG: CWD: {os.getcwd()}")
print(f"DEBUG: src content: {os.listdir('src')}")
if os.path.exists('src/quanttrade'):
    print(f"DEBUG: src/quanttrade content: {os.listdir('src/quanttrade')}")

from quanttrade.models.trainer import ModelTrainer
from quanttrade.backtest.engine import BacktestEngine

def main():
    # 1. Load Data
    data_path = '/Users/furkanyilmaz/Desktop/QuantTrade/data/master/master_df.csv'
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    
    # Convert date to datetime
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

    # 2. Define Features and Target
    # Selecting a subset of numeric features for initial training
    # IMPORTANT: Only use features that don't contain same-day information
    feature_cols = [
        'price_rsi_14', 'price_macd', 'price_macd_signal', 
        'price_sma_20', 'price_sma_50', 'price_sma_200',
        'price_vol_20d',  # Removed price_return_1d to prevent leakage
        'macro_usd_try', 'macro_bist100'
    ]
    
    # Ensure these columns exist
    available_features = [col for col in feature_cols if col in df.columns]
    if len(available_features) < len(feature_cols):
        print(f"Warning: Some features are missing. Using: {available_features}")
    
    target_col = 'y_5d_up' # Predicting if price will be higher in 5 days
    
    print(f"Features: {len(available_features)}")
    print(f"Target: {target_col}")

    # 3. Train Model (CatBoost)
    trainer = ModelTrainer(model_params={'iterations': 200, 'depth': 6, 'learning_rate': 0.1})
    
    # Prepare data (Time-series split)
    X_train, X_test, y_train, y_test = trainer.prepare_data(
        df, target_col, available_features, test_size=0.2, date_col='date'
    )
    
    trainer.train(X_train, y_train)
    
    # Evaluate
    print("\nEvaluating Model...")
    metrics = trainer.evaluate(X_test, y_test)
    print("Classification Report:")
    print(metrics['report'])
    
    # Save Model
    model_path = 'models/catboost_model.cbm'
    trainer.save_model(model_path)

    # 4. Backtest
    print("\nRunning Backtest...")
    
    # Generate predictions for the test set
    predictions = trainer.predict(X_test)
    
    # Align test data for backtest
    # We need the price data corresponding to X_test
    test_indices = X_test.index
    backtest_df = df.loc[test_indices].copy()
    
    engine = BacktestEngine(initial_capital=10000)
    results = engine.run_backtest(backtest_df, predictions, price_col='price_close')
    
    performance = engine.calculate_metrics(results)
    
    print("\nBacktest Results:")
    for k, v in performance.items():
        print(f"{k}: {v}")

    # Save Backtest Results
    results.to_csv('data/backtest_results.csv')
    print("\nBacktest results saved to data/backtest_results.csv")

if __name__ == "__main__":
    main()
