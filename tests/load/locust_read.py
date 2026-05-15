from locust import HttpUser, task, between

class SmartNotesReadUser(HttpUser):
    wait_time = between(1,2)

    @task(1)
    def root(self):
        self.client.get("/", name="GET /")

    @task(2)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(5)
    def list_notes(self):
        self.client.get("/notes", name="GET /notes")
    
    @task(5)
    def list_tasks(self):
        self.client.get("/tasks", name="GET /tasks")
