from locust import HttpUser, task, between

class ToxicModelUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(5)
    def predict_endpoint(self):
        payload = {
            "comment_text": "You are doing a fantastic job with Wikipedia moderation!",
            "caps_ratio": 0.05,
            "exclaim_count": 1,
            "bad_word_count": 0
        }
        self.client.post("/v1/predict", json=payload)

    @task(1)
    def health_endpoint(self):
        self.client.get("/health")