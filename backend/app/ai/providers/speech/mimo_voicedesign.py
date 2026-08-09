from app.ai.providers.base import ProviderFailure


class MiMoVoiceDesignProvider:
    """Feature-gated placeholder. Qualification showed that the prior `audio.voice` payload is unsupported."""
    provider_name = "MIMO"

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    async def synthesize(self, text: str, voice: str | None = None):
        raise ProviderFailure("Voice Design is unavailable until vendor parameters are confirmed and qualified")
