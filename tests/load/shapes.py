from locust import LoadTestShape


class StepSpikeShape(LoadTestShape):
    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 2},
        {"duration": 120, "users": 30, "spawn_rate": 5},
        {"duration": 180, "users": 60, "spawn_rate": 10},
        {"duration": 240, "users": 100, "spawn_rate": 20},
        {"duration": 300, "users": 150, "spawn_rate": 30},
        {"duration": 360, "users": 20, "spawn_rate": 30},
    ]

    def tick(self):
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])

        return None