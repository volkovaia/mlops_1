import hashlib
import os
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import auc, f1_score, precision_recall_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from toxic_service.features import transform_texts_to_df

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.localhost")
MODEL_NAME = "toxic-comment-clf"
GATE_METRIC = "pr_auc"
MIN_GAIN = 0.0001

mlflow.set_tracking_uri(MLFLOW_URI)
client = MlflowClient(tracking_uri=MLFLOW_URI)

EXPERIMENT_NAME = "toxic-comment-classification"
exp = client.get_experiment_by_name(EXPERIMENT_NAME)
if exp is None:
    # указываем, что артефакты должны проксироваться сервером по HTTP
    client.create_experiment(EXPERIMENT_NAME, artifact_location="mlflow-artifacts:/")
mlflow.set_experiment(EXPERIMENT_NAME)


def get_data_md5(file_path: Path) -> str:
    return hashlib.md5(file_path.read_bytes()).hexdigest()


def evaluate_gate(
    client: MlflowClient, model_name: str, new_version: str, new_score: float
) -> bool:
    client.set_registered_model_alias(model_name, "challenger", new_version)
    print(f"-> Assigned alias 'challenger' to version {new_version}")

    try:
        champion_ver = client.get_model_version_by_alias(model_name, "champion")
        champ_run = client.get_run(champion_ver.run_id)
        champ_score = float(champ_run.data.metrics.get(GATE_METRIC, 0.0))
        print(
            f"Current champion (v{champion_ver.version}) {GATE_METRIC}: {champ_score:.4f}"
        )
    except Exception:
        print("No current champion found. Promoting first model to champion!")
        client.set_registered_model_alias(model_name, "champion", new_version)
        return True

    delta = new_score - champ_score
    print(
        f"Comparison: New {new_score:.4f} vs Champion {champ_score:.4f} (Delta: {delta:+.4f}, Required: +{MIN_GAIN})"
    )

    if delta >= MIN_GAIN:
        print(f"-> GATE PASSED! Version {new_version} promoted to 'champion'!")
        client.set_registered_model_alias(model_name, "champion", new_version)
        return True
    else:
        print(f"-> GATE REJECTED. Version {new_version} remains only 'challenger'.")
        return False


def train(c_param: float = 1.0):
    data_path = Path("data/train.csv")
    if not data_path.exists():
        print("data/train.csv not found!")
        sys.exit(1)

    data_hash = get_data_md5(data_path)
    df = pd.read_csv(data_path).dropna()
    print("\n==========================================")
    print(
        f"Starting training with C={c_param}, data_md5={data_hash[:8]} ({len(df)} rows)"
    )

    train_df, val_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df["toxic"]
    )

    X_train = transform_texts_to_df(train_df["comment_text"].tolist())
    y_train = train_df["toxic"].values

    X_val = transform_texts_to_df(val_df["comment_text"].tolist())
    y_val = val_df["toxic"].values

    num_cols = ["caps_ratio", "exclaim_count", "bad_word_count"]
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "text",
                TfidfVectorizer(max_features=5000, ngram_range=(1, 2)),
                "comment_text",
            ),
            ("num", SimpleImputer(strategy="constant", fill_value=0.0), num_cols),
        ]
    )

    pipeline = Pipeline(
        [
            ("preprocessor", preprocessor),
            ("clf", LogisticRegression(C=c_param, max_iter=500, random_state=42)),
        ]
    )

    with mlflow.start_run():
        pipeline.fit(X_train, y_train)

        val_probs = pipeline.predict_proba(X_val)[:, 1]
        precisions, recalls, thresholds = precision_recall_curve(y_val, val_probs)
        pr_auc_score = float(auc(recalls, precisions))

        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-8)
        best_idx = np.argmax(f1_scores)
        best_threshold = (
            float(thresholds[best_idx]) if best_idx < len(thresholds) else 0.5
        )
        best_threshold = round(max(0.1, min(0.9, best_threshold)), 3)

        val_preds = (val_probs >= best_threshold).astype(int)
        val_f1 = float(f1_score(y_val, val_preds))

        # Логируем параметры и метрики
        mlflow.log_params(
            {
                "C": c_param,
                "data_md5": data_hash,
                "rows_count": len(df),
                "threshold": best_threshold,
            }
        )
        mlflow.log_metrics({"pr_auc": pr_auc_score, "f1_score": val_f1})

        # Логируем PR-кривую
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(recalls, precisions, label=f"PR-curve (AUC = {pr_auc_score:.4f})")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title(f"Precision-Recall Curve (C={c_param})")
        ax.grid(True)
        ax.legend()
        mlflow.log_figure(fig, "pr_curve.png")
        plt.close(fig)

        # Логируем метаданные в JSON
        metadata = {
            "model_name": MODEL_NAME,
            "threshold": best_threshold,
            "features": ["comment_text"],
            "data_md5": data_hash,
            "pr_auc": round(pr_auc_score, 4),
            "f1": round(val_f1, 4),
        }
        mlflow.log_dict(metadata, "metadata.json")

        # Регистрируем модель через cloudpickle
        print("Registering model in MLflow Registry...")
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
            serialization_format="cloudpickle",
        )

        os.makedirs("models", exist_ok=True)
        joblib.dump({"pipeline": pipeline, "metadata": metadata}, "models/model.joblib")

        client = MlflowClient()
        # находим последнюю зарегистрированную версию
        versions = client.search_model_versions(f"name='{MODEL_NAME}'")
        latest_version = str(max(versions, key=lambda v: int(v.version)).version)

        # Прогоняем валидационный гейт
        evaluate_gate(
            client=client,
            model_name=MODEL_NAME,
            new_version=latest_version,
            new_score=pr_auc_score,
        )


if __name__ == "__main__":
    c_val = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    train(c_param=c_val)
