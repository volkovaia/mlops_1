import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
import joblib
import mlflow
from mlflow.tracking import MlflowClient
from fastapi import FastAPI, HTTPException, Request, Response, status

from toxic_service.db import db
from toxic_service.features import transform_texts_to_df
from toxic_service.schemas import (
    BatchPredictRequest,
    BatchPredictResponse,
    PredictRequest,
    PredictResponse,
)

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("MODEL_NAME")
MODEL_ALIAS = os.getenv("MODEL_ALIAS", "champion")
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.mlflow.svc.cluster.local:5000")
LOCAL_MODEL_PATH = os.getenv("MODEL_PATH", "models/model.joblib")

model_pipeline = None
model_metadata = {}
current_model_version = "local"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_pipeline, model_metadata, current_model_version

    if MODEL_NAME:
        logger.info(f"Loading model '{MODEL_NAME}@{MODEL_ALIAS}' from MLflow at {MLFLOW_URI}...")
        try:
            mlflow.set_tracking_uri(MLFLOW_URI)
            client = MlflowClient(tracking_uri=MLFLOW_URI)
            
            # Получаем версию по алиасу
            model_ver_info = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
            current_model_version = f"v{model_ver_info.version}"
            logger.info(f"Resolved alias '{MODEL_ALIAS}' to version {current_model_version}")

            # Загружаем модель напрямую по стандартному URI MLflow
            model_uri = f"models:/{MODEL_NAME}@{MODEL_ALIAS}"
            model_pipeline = mlflow.sklearn.load_model(model_uri)

            # Получаем порог из run
            run = client.get_run(model_ver_info.run_id)
            threshold = float(run.data.params.get("threshold", 0.5))
            model_metadata = {"threshold": threshold, "model_version": current_model_version}
            logger.info(f"Successfully loaded {MODEL_NAME} {current_model_version} with threshold {threshold}")
        except Exception as e:
            logger.error(f"Failed to load model from MLflow: {e}")
            model_pipeline = None
    else:
        logger.info(f"MODEL_NAME not set. Falling back to local file {LOCAL_MODEL_PATH}...")
        try:
            bundle = joblib.load(LOCAL_MODEL_PATH)
            model_pipeline = bundle.get("pipeline")
            model_metadata = bundle.get("metadata", {"threshold": 0.5, "model_version": "local"})
            current_model_version = model_metadata.get("model_version", "local")
            logger.info(f"Loaded local model {current_model_version}")
        except Exception as e:
            logger.error(f"Failed to load local model: {e}")
            model_pipeline = None

    await db.connect()
    yield
    await db.close()


app = FastAPI(
    title="Toxic Comment Detection API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_predictions_middleware(request: Request, call_next):
    if not request.url.path.startswith("/v1/predict"):
        return await call_next(request)

    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    body_bytes = await request.body()
    try:
        features_json = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        features_json = {"raw_body": body_bytes.decode("utf-8", errors="ignore")}

    response: Response = await call_next(request)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    prediction = getattr(
        request.state,
        "prediction",
        {"error": "validation_failed" if response.status_code == 422 else "failed"},
    )

    await db.log_prediction(
        request_id=request_id,
        model_version=current_model_version,
        features=features_json,
        prediction=prediction,
        latency_ms=latency_ms,
        status_code=response.status_code,
    )

    return response


@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    return {
        "status": "ok",
        "model_version": current_model_version,
        "model_name": MODEL_NAME or "local",
    }


@app.get("/ready", status_code=status.HTTP_200_OK)
async def ready():
    if model_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not loaded",
        )
    return {"status": "ready"}


@app.post("/v1/predict", response_model=PredictResponse, status_code=status.HTTP_200_OK)
async def predict(payload: PredictRequest, request: Request):
    start_time = time.perf_counter()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if model_pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    threshold = model_metadata.get("threshold", 0.5)

    df = transform_texts_to_df([payload.comment_text])
    prob = float(model_pipeline.predict_proba(df)[0, 1])
    is_toxic = bool(prob >= threshold)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    prediction_data = {
        "is_toxic": is_toxic,
        "probability": round(prob, 4),
    }
    request.state.prediction = prediction_data

    return {
        "is_toxic": is_toxic,
        "probability": round(prob, 4),
        "model_version": current_model_version,
        "request_id": request_id,
        "latency_ms": latency_ms,
    }


@app.post("/v1/predict/batch", response_model=BatchPredictResponse, status_code=status.HTTP_200_OK)
async def predict_batch(payload: BatchPredictRequest, request: Request):
    start_time = time.perf_counter()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if model_pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    threshold = model_metadata.get("threshold", 0.5)

    texts = [row.comment_text for row in payload.rows]
    df = transform_texts_to_df(texts)

    probs = model_pipeline.predict_proba(df)[:, 1]
    predictions = (probs >= threshold).tolist()
    probabilities = [round(float(p), 4) for p in probs]
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    request.state.prediction = {
        "count": len(predictions),
        "predictions": predictions,
        "probabilities": probabilities,
    }

    return {
        "predictions": predictions,
        "probabilities": probabilities,
        "model_version": current_model_version,
        "request_id": request_id,
        "latency_ms": latency_ms,
    }