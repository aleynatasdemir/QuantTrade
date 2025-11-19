import pandas as pd
import numpy as np
from catboost import CatBoostClassifier, Pool
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import os
from typing import List, Tuple, Dict, Any

class ModelTrainer:
    def __init__(self, model_params: Dict[str, Any] = None):
        """
        Initialize the ModelTrainer with optional model parameters for CatBoost.
        
        Args:
            model_params: Dictionary of parameters for CatBoostClassifier.
        """
        self.default_params = {
            'iterations': 1000,
            'learning_rate': 0.05,
            'depth': 6,
            'loss_function': 'Logloss',
            'eval_metric': 'Accuracy',
            'verbose': 100,
            'random_seed': 42,
            'allow_writing_files': False,
            'early_stopping_rounds': 50
        }
        
        if model_params:
            self.default_params.update(model_params)
            
        self.model = CatBoostClassifier(**self.default_params)
        self.feature_cols = []
        self.target_col = ''

    def prepare_data(self, df: pd.DataFrame, target_col: str, feature_cols: List[str], 
                    val_size: float = 0.15, test_size: float = 0.15, date_col: str = 'date') -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """
        Prepare data for training, validation, and testing using time-series split.
        
        Args:
            df: Input DataFrame.
            target_col: Name of the target column.
            feature_cols: List of feature column names.
            val_size: Proportion of the dataset for validation.
            test_size: Proportion of the dataset for testing.
            date_col: Name of the date column for time-based sorting.
            
        Returns:
            X_train, X_val, X_test, y_train, y_val, y_test
        """
        self.feature_cols = feature_cols
        self.target_col = target_col
        
        # Drop rows with missing values in features or target
        data = df[feature_cols + [target_col]].dropna()
        
        # Sort by date if available to respect time series nature
        if date_col in df.columns:
            # We need to ensure we are sorting the subset correctly. 
            # Ideally, sort the original DF first, then slice.
            # Assuming 'df' passed in is already sorted or we sort it here using the index if it corresponds to date
            # But to be safe, let's rely on the caller to pass a sorted DF or sort by index if it's time-based.
            # If date_col is not in feature_cols, we can't use it for sorting here easily without keeping it.
            pass 
        
        X = data[feature_cols]
        y = data[target_col].astype(int)
        
        # Time-series split calculations
        n = len(X)
        test_n = int(n * test_size)
        val_n = int(n * val_size)
        train_n = n - test_n - val_n
        
        X_train = X.iloc[:train_n]
        y_train = y.iloc[:train_n]
        
        X_val = X.iloc[train_n:train_n+val_n]
        y_val = y.iloc[train_n:train_n+val_n]
        
        X_test = X.iloc[train_n+val_n:]
        y_test = y.iloc[train_n+val_n:]
        
        print(f"Data Split Summary:")
        print(f"Train set: {len(X_train)} rows ({len(X_train)/n:.1%})")
        print(f"Valid set: {len(X_val)} rows ({len(X_val)/n:.1%})")
        print(f"Test set : {len(X_test)} rows ({len(X_test)/n:.1%})")
        
        return X_train, X_val, X_test, y_train, y_val, y_test

    def train(self, X_train: pd.DataFrame, y_train: pd.Series, 
              X_val: pd.DataFrame, y_val: pd.Series, 
              cat_features: List[str] = None) -> None:
        """
        Train the CatBoost model with validation set for early stopping.
        """
        print(f"\nStarting training with {len(X_train)} samples...")
        self.model.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            cat_features=cat_features,
            plot=False
        )
        print("Training complete.")

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series, set_name: str = "Test") -> Dict[str, Any]:
        """
        Evaluate the model on a specific dataset.
        """
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True)
        conf_matrix = confusion_matrix(y_test, y_pred)
        
        print(f"\n--- {set_name} Set Evaluation ---")
        print(f"Accuracy: {accuracy:.4f}")
        print("Classification Report:")
        print(classification_report(y_test, y_pred))
        
        return {
            'accuracy': accuracy,
            'report': report,
            'confusion_matrix': conf_matrix
        }

    def plot_training_results(self, output_dir: str):
        """
        Plot training learning curves and save to file.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            results = self.model.get_evals_result()
            epochs = len(results['learn']['Logloss'])
            x_axis = range(0, epochs)
            
            fig, ax = plt.subplots(1, 2, figsize=(15, 5))
            
            # Logloss Plot
            ax[0].plot(x_axis, results['learn']['Logloss'], label='Train')
            ax[0].plot(x_axis, results['validation']['Logloss'], label='Validation')
            ax[0].legend()
            ax[0].set_title('Logloss')
            ax[0].set_xlabel('Epochs')
            ax[0].set_ylabel('Logloss')
            
            # Accuracy Plot (if available)
            if 'Accuracy' in results['learn']:
                ax[1].plot(x_axis, results['learn']['Accuracy'], label='Train')
                ax[1].plot(x_axis, results['validation']['Accuracy'], label='Validation')
                ax[1].legend()
                ax[1].set_title('Accuracy')
                ax[1].set_xlabel('Epochs')
                ax[1].set_ylabel('Accuracy')
            
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'learning_curves.png'))
            plt.close()
            print(f"Learning curves saved to {output_dir}/learning_curves.png")
            
        except Exception as e:
            print(f"Could not plot learning curves: {e}")

    def plot_feature_importance(self, output_dir: str):
        """
        Plot feature importance and save to file.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        feature_importance = self.model.feature_importances_
        sorted_idx = np.argsort(feature_importance)
        
        plt.figure(figsize=(10, 8))
        plt.barh(range(len(sorted_idx)), feature_importance[sorted_idx], align='center')
        plt.yticks(range(len(sorted_idx)), np.array(self.feature_cols)[sorted_idx])
        plt.xlabel('Importance')
        plt.title('Feature Importance')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'feature_importance.png'))
        plt.close()
        print(f"Feature importance saved to {output_dir}/feature_importance.png")

    def plot_confusion_matrix(self, y_true, y_pred, output_dir: str, set_name: str = "Test"):
        """
        Plot confusion matrix and save to file.
        """
        os.makedirs(output_dir, exist_ok=True)
        cm = confusion_matrix(y_true, y_pred)
        
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
        plt.title(f'Confusion Matrix ({set_name})')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f'confusion_matrix_{set_name.lower()}.png'))
        plt.close()
        print(f"Confusion matrix saved to {output_dir}/confusion_matrix_{set_name.lower()}.png")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Generate predictions.
        """
        return self.model.predict(X)

    def save_model(self, path: str) -> None:
        """
        Save the trained model to disk.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.model.save_model(path)
        print(f"Model saved to {path}")

    def load_model(self, path: str) -> None:
        """
        Load a trained model from disk.
        """
        self.model.load_model(path)
        print(f"Model loaded from {path}")
