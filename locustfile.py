from locust import HttpUser, between, task


class ToxicModelUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(5)
    def predict_endpoint(self):
        payload = {
            "comment_text": "This is a neutral and constructive Wikipedia discussion comment",
        }
        self.client.post("/v1/predict", json=payload)

    @task(1)
    def health_endpoint(self):
        self.client.get("/health")
