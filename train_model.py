import pandas as pd
import sys
import os

# Add src to python path
sys.path.append(os.path.abspath('src'))

from quanttrade.models.trainer import ModelTrainer

def main():
    print("="*50)
    print("QUANTTRADE MODEL TRAINING PIPELINE")
    print("="*50)

    # 1. Load Data
    data_path = '/Users/furkanyilmaz/Desktop/QuantTrade/data/master/master_df.csv'
    if not os.path.exists(data_path):
        print(f"Error: Data file not found at {data_path}")
        return

    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    
    # Convert date to datetime and sort
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    # 2. Define Features and Target
    # IMPORTANT: Excluding 'price_return_1d' and other same-day metrics to prevent leakage
    feature_cols = [
        'price_rsi_14', 
        'price_macd', 
        'price_macd_signal', 
        'price_sma_20', 
        'price_sma_50', 
        'price_sma_200',
        'price_vol_20d',
        # 'price_return_1d', # REMOVED due to leakage
        'macro_usd_try', 
        'macro_bist100'
    ]
    
    target_col = 'y_5d_up'
    
    # Check available features
    available_features = [col for col in feature_cols if col in df.columns]
    missing_features = list(set(feature_cols) - set(available_features))
    
    print(f"\nFeatures selected ({len(available_features)}):")
    for f in available_features:
        print(f"  - {f}")
        
    if missing_features:
        print(f"Warning: Missing features: {missing_features}")
        
    print(f"Target variable: {target_col}")

    # 3. Initialize Trainer
    # Using CatBoost with GPU if available, otherwise CPU
    # Increased iterations and added early stopping
    trainer = ModelTrainer(model_params={
        'iterations': 2000,
        'learning_rate': 0.03,
        'depth': 6,
        'early_stopping_rounds': 100,
        'verbose': 200
    })
    
    # 4. Prepare Data (Train / Validation / Test Split)
    print("\nPreparing data splits...")
    X_train, X_val, X_test, y_train, y_val, y_test = trainer.prepare_data(
        df, target_col, available_features, 
        val_size=0.15, test_size=0.15
    )
    
    # 5. Train Model
    print("\nTraining model...")
    trainer.train(X_train, y_train, X_val, y_val)
    
    # 6. Evaluate Model
    print("\nEvaluating model performance...")
    trainer.evaluate(X_val, y_val, set_name="Validation")
    trainer.evaluate(X_test, y_test, set_name="Test")
    
    # 7. Save Results and Plots
    output_dir = 'data/models/catboost_v1'
    print(f"\nSaving results to {output_dir}...")
    
    trainer.save_model(os.path.join(output_dir, 'model.cbm'))
    trainer.plot_training_results(output_dir)
    trainer.plot_feature_importance(output_dir)
    
    # Plot confusion matrices
    trainer.plot_confusion_matrix(y_val, trainer.predict(X_val), output_dir, set_name="Validation")
    trainer.plot_confusion_matrix(y_test, trainer.predict(X_test), output_dir, set_name="Test")
    
    print("\n" + "="*50)
    print("TRAINING COMPLETED SUCCESSFULLY")
    print(f"Check {output_dir} for plots and model file.")
    print("="*50)

if __name__ == "__main__":
    main()
