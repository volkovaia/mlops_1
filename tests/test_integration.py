import os

import asyncpg
import pytest
from fastapi.testclient import TestClient

from toxic_service.app import app

DATABASE_URL = os.getenv("DATABASE_URL")


@pytest.mark.skipif(
    not DATABASE_URL, reason="DATABASE_URL is not set (running unit tests)"
)
def test_db_logging_integration():
    """Проверка запись в БД успешного запроса (200) и запроса с ошибкой валидации (422)."""
    with TestClient(app) as client:
        # Успешный запрос (200 OK)
        good_payload = {"comment_text": "Neutral test message for integration test"}
        good_resp = client.post("/v1/predict", json=good_payload)
        assert good_resp.status_code == 200

        # Невалидный запрос (422 - лишнее поле)
        bad_payload = {"comment_text": "Hello", "extra_bad_field": 123}
        bad_resp = client.post("/v1/predict", json=bad_payload)
        assert bad_resp.status_code == 422

    # Подключаемся напрямую к Postgres и проверяем сохраненные строки
    import asyncio

    async def verify_records():
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            row_200 = await conn.fetchrow(
                "SELECT * FROM prediction_logs WHERE status_code = 200 ORDER BY id DESC LIMIT 1"
            )
            assert row_200 is not None
            assert row_200["status_code"] == 200
            assert "comment_text" in row_200["features"]

            row_422 = await conn.fetchrow(
                "SELECT * FROM prediction_logs WHERE status_code = 422 ORDER BY id DESC LIMIT 1"
            )
            assert row_422 is not None
            assert row_422["status_code"] == 422
            assert "extra_bad_field" in row_422["features"]
        finally:
            await conn.close()

    asyncio.run(verify_records())
