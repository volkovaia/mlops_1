from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment_text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Raw text of the Wikipedia comment"
    )
    caps_ratio: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Share of capital letters [0.0 - 1.0]"
    )
    exclaim_count: Optional[int] = Field(
        default=0,
        ge=0,
        le=500,
        description="Count of exclamation marks"
    )
    bad_word_count: Optional[int] = Field(
        default=0,
        ge=0,
        le=100,
        description="Count of profane words"
    )

class PredictResponse(BaseModel):
    is_toxic: bool
    probability: float
    model_version: str
    request_id: str
    latency_ms: float

# Схема для Звёздочки 2 
class BatchPredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: List[PredictRequest] = Field(..., min_length=1, max_length=1000)

class BatchPredictResponse(BaseModel):
    predictions: List[bool]
    probabilities: List[float]
    model_version: str
    request_id: str
    latency_ms: float