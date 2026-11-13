"""Drive business graph expansion while the scheduler resolves tasks."""


def run_pipeline(self):
    def update():
        records = self.scheduler.state["tasks"]
        ready = self.scheduler.dependencies_passed
        self.scheduler.expand_ready_partitions()
        api = records.get("api-index", {})
        if self.expand_api and ready(("api-index", "api-map")):
            self.scheduler.tasks.pop("api-parameters", None)
            expand = self.expand_api
            self.expand_api = None
            expand()
        elif self.expand_api and api.get("status") in {
            "failed",
            "rejected",
            "pending",
            "rate_limited",
            "awaiting_configuration",
            "budget_exhausted",
            "awaiting_answer",
            "awaiting_review",
            "blocked_dependency",
        }:
            # A blocked index still declares the final dependency target;
            # the scheduler will never treat it as a complete API table.
            active = (
                api.get("status") in {"failed", "rejected"}
                and api.get("rounds", 0) < self.scheduler.rounds
            )
            if not active:
                if "api-parameters" not in self.scheduler.tasks:
                    self.add(
                        "api-parameters",
                        "api-parameters",
                        ("api-index",),
                        transform=lambda d: {"apis": []},
                    )
                    self.scheduler.tasks["api-parameters"].deferred = True
        if self.expand_pipeline and ready(("use-case-align", "test-case-align")):
            expand = self.expand_pipeline
            self.expand_pipeline = None
            expand()
        self.scheduler.expand_ready_partitions()

    self.scheduler.on_update = update
    self.scheduler.on_result = self.publish_progress
    try:
        result = self.scheduler.run()
        if self.expand_api:
            self.scheduler.tasks.pop("api-parameters", None)
            expand = self.expand_api
            self.expand_api = None
            expand()
            result = self.scheduler.run()
        if self.expand_pipeline and all(
            self.scheduler.state["tasks"].get(k, {}).get("status") == "passed"
            for k in ("use-case-align", "test-case-align")
        ):
            expand = self.expand_pipeline
            self.expand_pipeline = None
            expand()
            result = self.scheduler.run()
        before = set(self.scheduler.tasks)
        update()
        if before != set(self.scheduler.tasks):
            result = self.scheduler.run()
        return result
    finally:
        self.scheduler.on_update = None
        self.scheduler.on_result = None
