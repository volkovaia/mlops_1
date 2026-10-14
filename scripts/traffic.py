import sys
import time
import random
import statistics
import requests

URL = "http://toxic.localhost/v1/predict"
HEALTH_URL = "http://toxic.localhost/health"

COMMENTS = [
    "Thank you for this constructive contribution to Wikipedia!",
    "Please adhere to the community guidelines and neutral point of view.",
    "This section looks well cited, great work on finding sources.",
    "You are an absolute idiot and completely useless moron!",
    "Shut up and stop editing this page immediately!",
    "I disagree with this opinion, let us discuss it on the talk page.",
    "Die die die I hate you so much you piece of trash!",
    "Great article expanding on the historical context.",
]

def main():
    print(f"Starting traffic generator hitting {URL}...")
    print("Press Ctrl+C to stop.\n")

    latencies = []
    status_counts = {}
    start_time = time.time()
    last_stat_time = start_time

    try:
        while True:
            text = random.choice(COMMENTS)
            payload = {"comment_text": text}
            req_start = time.perf_counter()

            try:
                resp = requests.post(URL, json=payload, timeout=2.0)
                code = resp.status_code
            except Exception as e:
                code = "ERR"

            lat_ms = (time.perf_counter() - req_start) * 1000
            latencies.append(lat_ms)
            status_counts[code] = status_counts.get(code, 0) + 1

            # Каждые 5 секунд выводим краткую сводку в консоль
            now = time.time()
            if now - last_stat_time >= 5.0:
                elapsed = now - last_stat_time
                rps = len(latencies) / elapsed
                p50 = statistics.median(latencies) if latencies else 0.0
                p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else p50

                # Заодно проверяем текущую активную версию в подах
                try:
                    h_resp = requests.get(HEALTH_URL, timeout=1.0).json()
                    curr_ver = h_resp.get("model_version", "unknown")
                except Exception:
                    curr_ver = "err"

                print(
                    f"[{time.strftime('%H:%M:%S')}] Active: {curr_ver} | "
                    f"RPS: {rps:5.1f} | Latency p50: {p50:4.1f}ms, p95: {p95:4.1f}ms | "
                    f"Statuses: {status_counts}"
                )

                latencies.clear()
                status_counts.clear()
                last_stat_time = now

            # Пауза между запросами (15–30 запросов в секунду)
            time.sleep(random.uniform(0.03, 0.07))

    except KeyboardInterrupt:
        print("\nTraffic generator stopped.")

if __name__ == "__main__":
    main()