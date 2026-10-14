import os
import sys

import mlflow
import pandas as pd
import pandera as pa
from pandera import Check, Column, DataFrameSchema

# Схема для строк
row_schema = DataFrameSchema({
    "comment_text": Column(
        str,
        checks=[
            Check(lambda s: s.str.len() >= 1, error="Текст не может быть пустым"),
            Check(lambda s: s.str.len() <= 10000, error="Текст превышает допустимый размер")
        ],
        nullable=False
    ),
    "toxic": Column(
        int,
        checks=[
            Check.isin([0, 1], error="Класс токсичности должен быть 0 или 1")
        ],
        nullable=False
    )
})

def validate_dataset(df: pd.DataFrame) -> bool:
    """Проверяет датасет по строкам и по распределению целиком."""
    errors = []
    
    # Проверка строк
    try:
        row_schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as err:
        errors.append(err.failure_cases)

    # Проверка распределения выгрузки целиком:
    # минимальный размер датасета
    if len(df) < 1000:
        errors.append(pd.DataFrame([{"check": "min_rows", "failure_case": len(df)}]))
    
    # Доля токсичного класса должна быть разумной 
    toxic_rate = df["toxic"].mean()
    if not (0.01 <= toxic_rate <= 0.90):
        errors.append(pd.DataFrame([{"check": "toxic_rate_bounds", "failure_case": toxic_rate}]))

    if errors:
        failures_df = pd.concat(errors, ignore_index=True) if len(errors) > 1 else errors[0]
        failures_df.to_csv("failure_cases.csv", index=False)
        return False
    return True

def run_validation(data_path: str = "data/train.csv"):
    df = pd.read_csv(data_path)
    is_valid = validate_dataset(df)
    
    # Логируем результат валидации в MLflow
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.mlflow.svc.cluster.local:5000"))
    mlflow.set_experiment("data-validation")
    with mlflow.start_run(run_name="validate"):
        mlflow.set_tag("valid", str(is_valid).lower())
        if not is_valid:
            mlflow.log_artifact("failure_cases.csv")
            print("Validation FAILED: failure_cases.csv logged to MLflow")
            sys.exit(1)
        print("Validation PASSED successfully!")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/train.csv"
    run_validation(path)