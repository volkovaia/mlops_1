import time
import uuid
from contextlib import asynccontextmanager
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, status
from toxic_service.db import db
from toxic_service.schemas import (
    PredictRequest,
    PredictResponse,
    BatchPredictRequest,
    BatchPredictResponse
)

MODEL_PATH = "models/model.joblib"
model_bundle = {}

NUMERIC_COLS = ["caps_ratio", "exclaim_count", "bad_word_count"]

def prepare_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Преобразует входные словари в DataFrame и безопасно обрабатывает None/NaN."""
    df = pd.DataFrame(rows)
    for col in NUMERIC_COLS:
        if col in df.columns:
            # Превращаем None в NaN, а затем в 0.0 нужного типа float
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0
    return df

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_bundle
    try:
        model_bundle = joblib.load(MODEL_PATH)
    except Exception as e:
        model_bundle = {}
    
    await db.connect()
    yield
    await db.close()

app = FastAPI(
    title="Toxic Comment Detection API",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    return {"status": "ok"}

@app.get("/ready", status_code=status.HTTP_200_OK)
async def ready():
    if not model_bundle or "pipeline" not in model_bundle:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not loaded"
        )
    return {"status": "ready"}

@app.post("/v1/predict", response_model=PredictResponse, status_code=status.HTTP_200_OK)
async def predict(payload: PredictRequest):
    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())

    if not model_bundle:
        raise HTTPException(status_code=503, detail="Model not loaded")

    pipeline = model_bundle["pipeline"]
    metadata = model_bundle["metadata"]

    raw_data = payload.model_dump()
    # Безопасная подготовка признаков с обработкой пропусков
    df = prepare_dataframe([raw_data])

    prob = float(pipeline.predict_proba(df)[0, 1])
    is_toxic = bool(prob >= metadata["threshold"])

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    response_data = {
        "is_toxic": is_toxic,
        "probability": round(prob, 4),
        "model_version": metadata["model_version"],
        "request_id": request_id,
        "latency_ms": latency_ms
    }

    # Логируем в БД (если база подключена)
    await db.log_prediction(
        request_id=request_id,
        model_version=metadata["model_version"],
        features=raw_data,
        prediction={"is_toxic": is_toxic, "probability": prob},
        latency_ms=latency_ms,
        status_code=status.HTTP_200_OK
    )

    return response_data

# Батч-эндпоинт (Звёздочка 2)
@app.post("/v1/predict/batch", response_model=BatchPredictResponse, status_code=status.HTTP_200_OK)
async def predict_batch(payload: BatchPredictRequest):
    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())

    if not model_bundle:
        raise HTTPException(status_code=503, detail="Model not loaded")

    pipeline = model_bundle["pipeline"]
    metadata = model_bundle["metadata"]

    rows_data = [row.model_dump() for row in payload.rows]
    df = prepare_dataframe(rows_data)

    probs = pipeline.predict_proba(df)[:, 1]
    predictions = (probs >= metadata["threshold"]).tolist()
    probabilities = [round(float(p), 4) for p in probs]

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return {
        "predictions": predictions,
        "probabilities": probabilities,
        "model_version": metadata["model_version"],
        "request_id": request_id,
        "latency_ms": latency_ms
    }