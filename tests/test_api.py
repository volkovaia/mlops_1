import pytest
from fastapi.testclient import TestClient
from toxic_service.app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_ready_check(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

def test_predict_smoke(client):
    payload = {"comment_text": "This is a great neutral contribution, thank you."}
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["is_toxic"], bool)
    assert isinstance(data["probability"], float)
    assert 0.0 <= data["probability"] <= 1.0
    assert "latency_ms" in data

def test_predict_contract_forbidden_client_meta_features(client):
    # Клиенту запрещено присылать мета-фичи 
    payload = {
        "comment_text": "Neutral text",
        "caps_ratio": 0.5
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422

def test_predict_contract_empty_text(client):
    payload = {"comment_text": ""}
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422

def test_predict_determinism(client):
    payload = {"comment_text": "You are an absolute idiot and moron!"}
    res1 = client.post("/v1/predict", json=payload).json()
    res2 = client.post("/v1/predict", json=payload).json()
    assert res1["is_toxic"] == res2["is_toxic"]
    assert res1["probability"] == res2["probability"]

def test_predict_batch(client):
    payload = {
        "rows": [
            {"comment_text": "Thank you for the help"},
            {"comment_text": "You are completely useless"}
        ]
    }
    response = client.post("/v1/predict/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["predictions"]) == 2