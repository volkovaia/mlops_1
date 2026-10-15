# Toxic Comment Classification Service (MLOps Production)

Production-ready микросервис для автоматической детекции токсичных комментариев на базе **FastAPI**, **scikit-learn**, **uv**, **DVC**, **MLflow**, **Airflow** и **Kubernetes (kind)**.

Сервис решает задачу бинарной классификации англоязычных комментариев (датасет Jigsaw Toxic Comment Classification Challenge). Модель представляет собой `Pipeline(ColumnTransformer[TfidfVectorizer + SimpleImputer], LogisticRegression)` с мета-признаками длины, капса и знаков препинания. Сервис принимает исключительно сырой текст (`comment_text`).

---

## Quickstart (Развёртывание с нуля)

Для воспроизведения проекта требуется Windows 11 / Linux с установленными Docker Desktop (WSL2), Python 3.12, `uv` и `kubectl`.

### 1. Клонирование и окружение
```bash
git clone https://github.com/volkovaia/mlops_1.git
cd mlops_1
uv sync
```

### 2. Развёртывание платформы

```bash
# Развёртывание kind-кластера с портами 80/443, Traefik, MLflow, Airflow, S3 RustFS, Prometheus и Grafana:
bash platform/up.sh

# В среде Windows PowerShell:
& "C:\Program Files\Git\bin\bash.exe" platform/up.sh
```

### 3. Данные и запуск сервиса
```bash
# Пуш версионированных данных в S3 RustFS кластера
uv run dvc push -r laptop

# Применение манифестов сервиса
kubectl apply -f k8s/
kubectl rollout status deployment/toxic-service -n default --timeout=120s
```

### 4. Проверка работы сервиса через Ingress
```bash
curl -X POST http://toxic.localhost/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"comment_text": "Thank you very much for your great assistance!"}'
  ```

## Адреса интерфейсов

| Сервис | Локальный URL | Учётные данные |
|---|---|---|
| Toxic Service API | http://toxic.localhost | — |
| MLflow Model Registry | http://mlflow.localhost | — |
| Apache Airflow | http://airflow.localhost | `admin` / `admin` |
| Grafana Dashboards | http://grafana.localhost | `admin` / `admin` |
| S3 RustFS Console | http://s3-console.localhost | `dvcadmin` / `dvc-secret-123` |

## Ручной запуск конвейера переобучения

1. Откройте веб-интерфейс Airflow: [http://airflow.localhost](http://airflow.localhost).
2. Включите тумблер у DAG `toxic_retrain`.
3. Нажмите кнопку **Trigger DAG** (▶).

Запустится цепочка из 4 задач:

- **validate** — скачивание данных через DVC и валидация схемы через Pandera.
- **train** — обучение в изолированном поде, логирование в MLflow и проверка качества валидационным гейтом.
- **promoted** — проверка статуса `@champion` через MLflow REST API.
- **rollout** — Zero-Downtime перезапуск подов сервиса в Kubernetes.