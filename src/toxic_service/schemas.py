from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment_text: str = Field(
        ..., min_length=1, max_length=5000, description="Raw text of the comment"
    )


class PredictResponse(BaseModel):
    is_toxic: bool
    probability: float
    model_version: str
    request_id: str
    latency_ms: float


class BatchPredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[PredictRequest] = Field(..., min_length=1, max_length=1000)


class BatchPredictResponse(BaseModel):
    predictions: list[bool]
    probabilities: list[float]
    model_version: str
    request_id: str
    latency_ms: float
