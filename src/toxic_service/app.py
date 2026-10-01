# src/toxic_service/app.py
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import joblib
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

MODEL_PATH = os.getenv("MODEL_PATH", "models/model.joblib")
model_bundle = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_bundle
    try:
        model_bundle = joblib.load(MODEL_PATH)
        logger.info(f"Model successfully loaded from {MODEL_PATH}")
    except Exception as e:
        logger.error(f"Failed to load model from {MODEL_PATH}: {e}")
        model_bundle = {}

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
    # сохраняем request_id в state, чтобы хендлер вернул клиенту точно такой же ID
    request.state.request_id = request_id

    body_bytes = await request.body()
    try:
        features_json = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        features_json = {"raw_body": body_bytes.decode("utf-8", errors="ignore")}

    response: Response = await call_next(request)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    model_version = model_bundle.get("metadata", {}).get("model_version", "1.0.0")

    # реальное предсказание из request.state или ошибку 
    prediction = getattr(
        request.state,
        "prediction",
        {"error": "validation_failed" if response.status_code == 422 else "failed"},
    )

    await db.log_prediction(
        request_id=request_id,
        model_version=model_version,
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
        "model_path": MODEL_PATH,
    }


@app.get("/ready", status_code=status.HTTP_200_OK)
async def ready():
    if not model_bundle or "pipeline" not in model_bundle:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not loaded",
        )
    return {"status": "ready"}


@app.post("/v1/predict", response_model=PredictResponse, status_code=status.HTTP_200_OK)
async def predict(payload: PredictRequest, request: Request):
    start_time = time.perf_counter()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if not model_bundle:
        raise HTTPException(status_code=503, detail="Model not loaded")

    pipeline = model_bundle["pipeline"]
    metadata = model_bundle["metadata"]

    df = transform_texts_to_df([payload.comment_text])
    prob = float(pipeline.predict_proba(df)[0, 1])
    is_toxic = bool(prob >= metadata["threshold"])
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Сохраняем предсказание в state для middleware
    request.state.prediction = {
        "is_toxic": is_toxic,
        "probability": round(prob, 4),
    }

    return {
        "is_toxic": is_toxic,
        "probability": round(prob, 4),
        "model_version": metadata["model_version"],
        "request_id": request_id,
        "latency_ms": latency_ms,
    }


@app.post("/v1/predict/batch", response_model=BatchPredictResponse, status_code=status.HTTP_200_OK)
async def predict_batch(payload: BatchPredictRequest, request: Request):
    start_time = time.perf_counter()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if not model_bundle:
        raise HTTPException(status_code=503, detail="Model not loaded")

    pipeline = model_bundle["pipeline"]
    metadata = model_bundle["metadata"]

    texts = [row.comment_text for row in payload.rows]
    df = transform_texts_to_df(texts)

    probs = pipeline.predict_proba(df)[:, 1]
    predictions = (probs >= metadata["threshold"]).tolist()
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
        "model_version": metadata["model_version"],
        "request_id": request_id,
        "latency_ms": latency_ms,
    }