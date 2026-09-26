# scripts/train.py
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from toxic_service.features import transform_texts_to_df
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

def load_data() -> pd.DataFrame:
    """Загружает датасет Jigsaw: локальный файл или скачивает реальный срез."""
    possible_paths = [
        "data/train.csv",
        "train.csv",
        "data/jigsaw_sample.csv"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Loading local dataset from {path}...")
            df = pd.read_csv(path)
            # В Jigsaw колонка текста называется 'comment_text', таргет 'toxic'
            if "comment_text" in df.columns and "toxic" in df.columns:
                return df[["comment_text", "toxic"]].dropna().sample(n=min(len(df), 20000), random_state=42)
    
    print("Local train.csv not found. Downloading Jigsaw subset from GitHub mirror...")
    url = "https://raw.githubusercontent.com/t-davidson/hate-speech-and-offensive-language/master/data/labeled_data.csv"
    try:
        raw_df = pd.read_csv(url)
        # Мапим hate_speech / offensive в бинарный toxic
        raw_df["toxic"] = (raw_df["class"] < 2).astype(int)
        raw_df["comment_text"] = raw_df["tweet"]
        return raw_df[["comment_text", "toxic"]].sample(n=min(len(raw_df), 15000), random_state=42)
    except Exception as e:
        print(f"Fallback due to connection: {e}")
        # Запасной синтез достаточного объема
        texts = [
            "Great neutral article, thanks for your help",
            "You are a stupid idiot and moron",
            "Please follow Wikipedia neutrality guidelines",
            "Shut up you horrible trash, die die die",
            "This edit seems constructive and well referenced",
            "Get out of here before I hurt you",
            "I disagree with this section, let us discuss on talk page",
            "Completely useless piece of garbage",
        ] * 1000
        labels = [0, 1, 0, 1, 0, 1, 0, 1] * 1000
        return pd.DataFrame({"comment_text": texts, "toxic": labels})

def train():
    os.makedirs("models", exist_ok=True)
    df = load_data()
    print(f"Training on {len(df)} samples with label balance: {df['toxic'].mean():.2%}")

    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["toxic"])

    # Извлекаем мета-признаки через единый модуль сервиса
    print("Extracting meta features")
    X_train = transform_texts_to_df(train_df["comment_text"].tolist())
    y_train = train_df["toxic"].values

    X_val = transform_texts_to_df(val_df["comment_text"].tolist())
    y_val = val_df["toxic"].values

    num_cols = ["caps_ratio", "exclaim_count", "bad_word_count"]
    preprocessor = ColumnTransformer(
        transformers=[
            ("text", TfidfVectorizer(max_features=5000, ngram_range=(1, 2)), "comment_text"),
            ("num", SimpleImputer(strategy="constant", fill_value=0.0), num_cols),
        ]
    )

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("clf", LogisticRegression(C=3.0, max_iter=500, random_state=42))
    ])

    print("Fitting pipeline...")
    pipeline.fit(X_train, y_train)

    # Подбор оптимального порога по F1-score на валидации
    val_probs = pipeline.predict_proba(X_val)[:, 1]
    precisions, recalls, thresholds = precision_recall_curve(y_val, val_probs)
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-8)
    best_idx = np.argmax(f1_scores)
    best_threshold = float(thresholds[best_idx]) if best_idx < len(thresholds) else 0.5
    best_threshold = round(max(0.1, min(0.9, best_threshold)), 3)

    val_preds = (val_probs >= best_threshold).astype(int)
    val_f1 = f1_score(y_val, val_preds)
    print(f"Optimal threshold: {best_threshold}, Validation F1: {val_f1:.4f}")

    metadata = {
        "model_name": "toxic_comment_logreg",
        "model_version": "1.0.0",
        "feature_names": ["comment_text"],  # (клиент передает только текст)
        "calculated_meta_features": num_cols,
        "threshold": best_threshold,
        "validation_f1": round(float(val_f1), 4),
        "target": "is_toxic"
    }

    bundle = {
        "pipeline": pipeline,
        "metadata": metadata
    }

    joblib.dump(bundle, "models/model.joblib")
    print("Model saved to models/model.joblib")

if __name__ == "__main__":
    train()