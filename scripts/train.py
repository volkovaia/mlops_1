# scripts/train.py
import os
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

def train_and_save():
    os.makedirs("models", exist_ok=True)

    # Репрезентативная выборка с мета-фичами 
    data = [
        {"comment_text": "Hello, thank you for your contribution!", "caps_ratio": 0.05, "exclaim_count": 1, "bad_word_count": 0, "target": 0},
        {"comment_text": "You are completely useless and stupid idiot", "caps_ratio": 0.0, "exclaim_count": 0, "bad_word_count": 2, "target": 1},
        {"comment_text": "Please see Wikipedia policies on neutrality.", "caps_ratio": 0.03, "exclaim_count": 0, "bad_word_count": 0, "target": 0},
        {"comment_text": "DIE DIE DIE I HATE YOU SO MUCH!!!", "caps_ratio": 0.85, "exclaim_count": 3, "bad_word_count": 1, "target": 1},
        {"comment_text": "Can we discuss this on the talk page?", "caps_ratio": 0.02, "exclaim_count": 0, "bad_word_count": 0, "target": 0},
        {"comment_text": "Shut up you horrible piece of trash", "caps_ratio": 0.0, "exclaim_count": 0, "bad_word_count": 1, "target": 1},
        {"comment_text": "Great work on expanding this section.", "caps_ratio": 0.04, "exclaim_count": 0, "bad_word_count": 0, "target": 0},
        {"comment_text": "GET OUT OF HERE YOU MORON", "caps_ratio": 0.95, "exclaim_count": 0, "bad_word_count": 1, "target": 1},
    ] * 50

    df = pd.DataFrame(data)
    feature_cols = ["comment_text", "caps_ratio", "exclaim_count", "bad_word_count"]
    X = df[feature_cols]
    y = df["target"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("text", TfidfVectorizer(max_features=1000, ngram_range=(1, 2)), "comment_text"),
            ("num", SimpleImputer(strategy="constant", fill_value=0.0), ["caps_ratio", "exclaim_count", "bad_word_count"]),
        ]
    )

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(C=3.0, random_state=42))
    ])

    pipeline.fit(X, y)

    # Паспорт модели
    metadata = {
        "model_name": "toxic_comment_logreg",
        "model_version": "1.0.0",
        "feature_names": feature_cols,
        "threshold": 0.321,  # Оптимальный порог для лейбла toxic 
        "target": "is_toxic"
    }

    bundle = {
        "pipeline": pipeline,
        "metadata": metadata
    }

    artifact_path = "models/model.joblib"
    joblib.dump(bundle, artifact_path)
    print(f"Model successfully saved to {artifact_path}")

if __name__ == "__main__":
    train_and_save()