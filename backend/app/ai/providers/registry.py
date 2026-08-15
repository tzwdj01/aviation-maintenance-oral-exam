from app.ai.providers.base import EvaluationProvider, SpeechProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._evaluation: dict[str, EvaluationProvider] = {}
        self._speech: dict[str, SpeechProvider] = {}

    def register_evaluation(self, name: str, provider: EvaluationProvider) -> None:
        self._evaluation[name.upper()] = provider

    def register_speech(self, name: str, provider: SpeechProvider) -> None:
        self._speech[name.upper()] = provider

    def evaluation(self, provider: str) -> EvaluationProvider:
        try:
            return self._evaluation[provider.upper()]
        except KeyError as exc:
            raise KeyError(f"No evaluation provider registered for {provider}") from exc

    def speech(self, provider: str) -> SpeechProvider:
        try:
            return self._speech[provider.upper()]
        except KeyError as exc:
            raise KeyError(f"No speech provider registered for {provider}") from exc
