from app.ai.providers.evaluation.deepseek import DeepSeekEvaluationProvider


class MiMoEvaluationProvider(DeepSeekEvaluationProvider):
    """Implemented for diagnostics only: its seeded LLM profile is FAILED, never formally qualified."""
    provider_name = "MIMO"
