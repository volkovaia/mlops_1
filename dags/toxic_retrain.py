import json
import os
import urllib.request
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import ShortCircuitOperator
from airflow.providers.cncf.kubernetes.operators.pod import (
    KubernetesPodOperator,
)
from kubernetes.client import models as k8s

IMAGE_NAME = os.getenv("TOXIC_SERVICE_IMAGE", "toxic-service:latest")
MLFLOW_URI = os.getenv(
    "MLFLOW_TRACKING_URI", "http://mlflow.mlflow.svc.cluster.local:5000"
)
MODEL_NAME = "toxic-comment-clf"

# Переменные окружения для подключения к S3 (RustFS) внутри кластера
s3_env = [
    k8s.V1EnvVar(name="AWS_ACCESS_KEY_ID", value="dvcadmin"),
    k8s.V1EnvVar(name="AWS_SECRET_ACCESS_KEY", value="dvc-secret-123"),
    k8s.V1EnvVar(
        name="MLFLOW_TRACKING_URI",
        value="http://mlflow.mlflow.svc.cluster.local:5000",
    ),
]

default_args = {
    "owner": "mlops",
    "depends_on_past": False,
    "retries": 0,
}

with DAG(
    dag_id="toxic_retrain",
    default_args=default_args,
    description="Validation, training with gate and rollout",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["mlops", "toxic-service"],
) as dag:
    # Валидация данных через Pandera
    validate_task = KubernetesPodOperator(
        task_id="validate",
        name="toxic-validate-pod",
        namespace="airflow",
        image=IMAGE_NAME,
        image_pull_policy="Never",
        cmds=["/bin/sh", "-c"],
        arguments=[
            "uv run dvc pull -r cluster data/train.csv.dvc && python -m"
            " toxic_service.data data/train.csv"
        ],
        env_vars=s3_env,
        get_logs=True,
        is_delete_operator_pod=True,
    )

    # Обучение модели с валидационным гейтом
    train_task = KubernetesPodOperator(
        task_id="train",
        name="toxic-train-pod",
        namespace="airflow",
        image=IMAGE_NAME,
        image_pull_policy="Never",
        cmds=["/bin/sh", "-c"],
        arguments=[
            "uv run dvc pull -r cluster data/train.csv.dvc && python scripts/train.py 20.0"
        ],
        env_vars=s3_env,
        get_logs=True,
        is_delete_operator_pod=True,
    )

    # Проверка через MLflow REST API: стал ли новый запуск чемпионом
    def check_if_promoted(**context):
        try:
            # Запрашиваем версию чемпиона
            champ_url = f"{MLFLOW_URI}/api/2.0/mlflow/registered-models/alias?name={MODEL_NAME}&alias=champion"
            req_champ = urllib.request.Request(champ_url)
            with urllib.request.urlopen(req_champ, timeout=10) as resp:
                champ_data = json.loads(resp.read().decode())
                champ_ver = champ_data.get("model_version", {}).get("version")

            # Запрашиваем список всех версий модели
            model_url = f"{MLFLOW_URI}/api/2.0/mlflow/registered-models/get?name={MODEL_NAME}"
            req_model = urllib.request.Request(model_url)
            with urllib.request.urlopen(req_model, timeout=10) as resp:
                model_data = json.loads(resp.read().decode())
                versions = model_data.get("registered_model", {}).get(
                    "latest_versions", []
                )
                latest_ver = str(max(int(v["version"]) for v in versions))

            is_promoted = str(champ_ver) == str(latest_ver)
            print(
                f"Latest version in registry: {latest_ver}, Champion version:"
                f" {champ_ver}. Promoted: {is_promoted}"
            )
            return is_promoted
        except Exception as e:
            print(f"Error checking champion status via MLflow REST API: {e}")
            return False

    promoted_task = ShortCircuitOperator(
        task_id="promoted",
        python_callable=check_if_promoted,
    )

    # Перезапуск деплоймента сервиса в namespace default
    rollout_task = BashOperator(
        task_id="rollout",
        bash_command=(
            "kubectl rollout restart deployment/toxic-service -n default && "
            "kubectl rollout status deployment/toxic-service -n default"
            " --timeout=120s"
        ),
    )

    validate_task >> train_task >> promoted_task >> rollout_task