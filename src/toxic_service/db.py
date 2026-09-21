import json
import logging
import os
from typing import Optional, Any
import asyncpg

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_logs (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_version VARCHAR(32) NOT NULL,
    features JSONB NOT NULL,
    prediction JSONB NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL,
    status_code INTEGER NOT NULL
);
"""

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.db_url = os.getenv("DATABASE_URL")

    async def connect(self):
        if not self.db_url:
            logger.warning("DATABASE_URL is not set. Database logging disabled.")
            return

        try:
            self.pool = await asyncpg.create_pool(dsn=self.db_url, min_size=1, max_size=10)
            async with self.pool.acquire() as conn:
                await conn.execute(CREATE_TABLE_SQL)
            logger.info("Successfully connected to Postgres and initialized tables.")
        except Exception as e:
            logger.error(f"Failed to connect to Postgres: {e}. Logging disabled.")
            self.pool = None

    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Postgres connection pool closed.")

    async def log_prediction(
        self,
        request_id: str,
        model_version: str,
        features: Any,
        prediction: Any,
        latency_ms: float,
        status_code: int = 200
    ):
        if not self.pool:
            return

        query = """
        INSERT INTO prediction_logs 
        (request_id, model_version, features, prediction, latency_ms, status_code)
        VALUES ($1, $2, $3, $4, $5, $6);
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    request_id,
                    model_version,
                    json.dumps(features),
                    json.dumps(prediction),
                    latency_ms,
                    status_code
                )
        except Exception as e:
            logger.error(f"Failed to write prediction log: {e}")

db = Database()