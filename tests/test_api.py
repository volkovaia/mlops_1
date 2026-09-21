import pytest
from fastapi.testclient import TestClient
from toxic_service.app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

# Health probe
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

# Ready probe
def test_ready_check(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

# Smoke: типы и допустимые границы
def test_predict_smoke(client):
    payload = {
        "comment_text": "This is a great article, thank you.",
        "caps_ratio": 0.05,
        "exclaim_count": 0,
        "bad_word_count": 0
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data["is_toxic"], bool)
    assert isinstance(data["probability"], float)
    assert 0.0 <= data["probability"] <= 1.0
    assert data["model_version"] == "1.0.0"
    assert "request_id" in data
    assert data["latency_ms"] >= 0.0

# Контракт: extra="forbid" вызывает 422
def test_predict_contract_forbidden_extra_fields(client):
    payload = {
        "comment_text": "Neutral comment",
        "unexpected_field": "hacking_attempt"
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422

# Контракт: выход за границы диапазонов вызывает 422
def test_predict_contract_invalid_boundaries(client):
    # caps_ratio должно быть <= 1.0
    payload = {
        "comment_text": "Bad comment",
        "caps_ratio": 1.5
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422

# Детерминизм: одинаковый вход дает одинаковый выход
def test_predict_determinism(client):
    payload = {
        "comment_text": "You are a horrible person and an idiot",
        "caps_ratio": 0.1,
        "exclaim_count": 0,
        "bad_word_count": 1
    }
    res1 = client.post("/v1/predict", json=payload).json()
    res2 = client.post("/v1/predict", json=payload).json()

    assert res1["is_toxic"] == res2["is_toxic"]
    assert res1["probability"] == res2["probability"]

# Поддержка опциональных полей
def test_predict_optional_fields_imputed(client):
    payload = {
        "comment_text": "Short neutral text without optional fields"
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    assert "is_toxic" in response.json()

# Батч-эндпоинт
def test_predict_batch(client):
    payload = {
        "rows": [
            {"comment_text": "Thanks for help"},
            {"comment_text": "Go to hell idiot"}
        ]
    }
    response = client.post("/v1/predict/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["predictions"]) == 2
    assert len(data["probabilities"]) == 2