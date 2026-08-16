"""Speech Qualification harness (Sprint 1B Formal Speech Qualification Gate).

Run against the real MiMo API with credentials injected via the environment
(``MIMO_API_KEY`` et al.). Never prints or persists credentials. Human-speech cases
require an external audio directory (``--audio-dir``) and are skipped (recorded as
``not_evaluated``) when no audio is provided — TTS-synthetic audio alone is not treated
as real-speech evidence (docs/qualification/SPEECH_QUALIFICATION.md).
"""
