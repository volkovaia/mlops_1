# scripts/bench_batch.py
import time
import httpx
import numpy as np

single_row = {"comment_text": "Neutral test comment for latency measurement"}
batch_500 = {"rows": [single_row] * 500}

url_single = "http://127.0.0.1:8000/v1/predict"
url_batch = "http://127.0.0.1:8000/v1/predict/batch"

client = httpx.Client()

latencies_1 = [client.post(url_single, json=single_row).json()["latency_ms"] for _ in range(15)]
latencies_500 = [client.post(url_batch, json=batch_500).json()["latency_ms"] for _ in range(15)]

print(f"Median 1 row: {np.median(latencies_1):.2f} ms")
print(f"Median 500 rows: {np.median(latencies_500):.2f} ms")
print(f"Ratio: {np.median(latencies_500) / np.median(latencies_1):.2f}x")