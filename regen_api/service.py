from .foundry import safe_failure


class SubmissionService:
    def __init__(self, store, gateway, settings):
        self.store, self.gateway, self.settings = store, gateway, settings

    def _analyze(self, attempt):
        # Source and RUNNING state are already committed; never hold a DB lock across Azure.
        try:
            result = self.gateway.analyze(attempt["description"])
        except Exception as exc:
            self.store.finish_attempt(attempt["attempt_id"], failure=safe_failure(exc))
        else:
            self.store.finish_attempt(attempt["attempt_id"], result=result)
        return self.store.get(attempt["id"])

    def create(self, input):
        return self._analyze(self.store.create(input.description, self.settings.agent_name, self.settings.agent_version))

    def revise(self, id, input):
        return self._analyze(self.store.begin_attempt(id, input.expected_version, self.settings.agent_name,
                                                     self.settings.agent_version, input.description))

    def retry(self, id, input):
        return self._analyze(self.store.begin_attempt(id, input.expected_version, self.settings.agent_name,
                                                     self.settings.agent_version))

    def review(self, id, input):
        return self.store.review(id, input)
