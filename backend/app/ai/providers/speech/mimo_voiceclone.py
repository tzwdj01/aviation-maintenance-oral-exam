from app.ai.providers.base import ProviderFailure


class MiMoVoiceCloneProvider:
    """Feature-gated placeholder; no unqualified clone payload is sent to the vendor."""
    provider_name = "MIMO"

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    async def synthesize(self, text: str, voice: str | None = None):
        raise ProviderFailure("Voice Clone is unavailable until authorized reference flow is confirmed and qualified")
