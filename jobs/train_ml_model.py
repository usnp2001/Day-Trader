# train_ml_model.py - AI Stock Prediction LightGBM Model Trainer
#
# GOOGLE COLAB INSTRUCTIONS:
# 1. Open Google Colab (https://colab.research.google.com).
# 2. Upload the generated dataset "ml_stock_dataset.csv" to your Colab environment.
# 3. Create a code cell and run:
#    !pip install lightgbm scikit-learn pandas numpy
# 4. Copy-paste this script or upload it and run:
#    %run train_ml_model.py

import os
import pandas as pd
import numpy as np
import pickle

# Import ML libraries with fallbacks
try:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, roc_auc_score, precision_score, recall_score, f1_score
    import lightgbm as lgb
    ML_LIBS_AVAILABLE = True
except ImportError:
    ML_LIBS_AVAILABLE = False

def prepare_dataset(csv_path: str):
    """Loads dataset, calculates features and constructs the target label."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}. Please run collect_ml_data.py first.")
        
    print(f"[ML Trainer] Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path)
    df = df.sort_values(by=["symbol", "date"]).reset_index(drop=True)
    
    print("[ML Trainer] Constructing target labels and features...")
    processed_dfs = []
    
    for sym, gp in df.groupby("symbol"):
        gp = gp.copy()
        
        # 1. Construct target: 1 if future 5-day max close >= 1.05 * current close, else 0
        # Reverse rolling max allows us to compute the max of future close prices
        future_max = gp["close"].iloc[::-1].rolling(window=5, min_periods=1).max().iloc[::-1].shift(-1)
        gp["target"] = (future_max / gp["close"] >= 1.05).astype(int)
        
        # Avoid incomplete windows at the end of the time series
        gp.iloc[-5:, gp.columns.get_loc("target")] = np.nan
        
        # 2. Construct Features
        gp["close_to_ma5"] = gp["close"] / (gp["ma5"] + 1e-9)
        gp["close_to_ma20"] = gp["close"] / (gp["ma20"] + 1e-9)
        gp["ma5_to_ma20"] = gp["ma5"] / (gp["ma20"] + 1e-9)
        
        gp["volume_ratio"] = gp["volume"] / (gp["volume"].rolling(5).mean() + 1e-9)
        
        gp["foreign_ratio"] = gp["foreign_net_buy"] / (gp["volume"] + 1e-9)
        gp["trust_ratio"] = gp["trust_net_buy"] / (gp["volume"] + 1e-9)
        gp["dealer_ratio"] = gp["dealer_net_buy"] / (gp["volume"] + 1e-9)
        
        gp["margin_ratio"] = gp["margin_balance"] / (gp["volume"] + 1e-9)
        gp["short_ratio"] = gp["short_balance"] / (gp["volume"] + 1e-9)
        
        processed_dfs.append(gp)
        
    df_feat = pd.concat(processed_dfs, ignore_index=True)
    
    # Drop rows with NaN targets
    df_feat = df_feat.dropna(subset=["target"]).reset_index(drop=True)
    return df_feat

def main():
    if not ML_LIBS_AVAILABLE:
        print("\n" + "="*70)
        print(" ERROR: Machine learning libraries (lightgbm, scikit-learn) are not installed!")
        print(" To run this locally, please execute:")
        print("    pip install lightgbm scikit-learn pandas numpy")
        print("\n Alternatively, upload this script and 'ml_stock_dataset.csv' to Google Colab.")
        print("="*70 + "\n")
        return
        
    csv_path = os.path.join(os.path.dirname(__file__), "ml_stock_dataset.csv")
    try:
        df = prepare_dataset(csv_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
        
    # Feature columns to train on
    feature_cols = [
        "close_to_ma5", "close_to_ma20", "ma5_to_ma20",
        "volume_ratio", "rsi_14", "kd_k", "kd_d",
        "macd_dif", "macd_dem", "macd_osc",
        "foreign_ratio", "trust_ratio", "dealer_ratio",
        "margin_ratio", "short_ratio"
    ]
    
    # Chronological Split to prevent look-ahead bias
    # We sort by date and split the last 20% of dates as validation/testing
    dates = sorted(df["date"].unique())
    split_idx = int(len(dates) * 0.8)
    split_date = dates[split_idx]
    
    print(f"[ML Trainer] Chronological split date: {split_date} (80% Train, 20% Val)")
    
    train_df = df[df["date"] < split_date]
    val_df = df[df["date"] >= split_date]
    
    X_train = train_df[feature_cols]
    y_train = train_df["target"]
    X_val = val_df[feature_cols]
    y_val = val_df["target"]
    
    print(f"[ML Trainer] Train samples: {len(X_train)} (Positive class ratio: {y_train.mean():.2%})")
    print(f"[ML Trainer] Val samples: {len(X_val)} (Positive class ratio: {y_val.mean():.2%})")
    
    # Train LightGBM model
    print("[ML Trainer] Training LightGBM Classifier...")
    model = lgb.LGBMClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        random_state=42,
        class_weight="balanced" # Handle class imbalance
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=10, verbose=False)]
    )
    
    # Predict and Evaluate
    y_pred = model.predict(X_val)
    y_prob = model.predict_proba(X_val)[:, 1]
    
    print("\n" + "="*50)
    print(" MODEL PERFORMANCE EVALUATION (Validation Set)")
    print("="*50)
    print(classification_report(y_val, y_pred))
    print(f"ROC AUC Score: {roc_auc_score(y_val, y_prob):.4f}")
    print(f"Precision: {precision_score(y_val, y_pred):.4f}")
    print(f"Recall:    {recall_score(y_val, y_pred):.4f}")
    print(f"F1-Score:  {f1_score(y_val, y_pred):.4f}")
    print("="*50)
    
    # Feature Importances
    importances = pd.DataFrame({
        "Feature": feature_cols,
        "Importance": model.feature_importances_
    }).sort_values(by="Importance", ascending=False)
    
    print("\nFeature Importances:")
    print(importances.to_string(index=False))
    
    # Export Model to PKL
    model_path = os.path.join(os.path.dirname(__file__), "ai_stock_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"\n[ML Trainer] Model successfully trained and exported to: {model_path}")

if __name__ == "__main__":
    main()
