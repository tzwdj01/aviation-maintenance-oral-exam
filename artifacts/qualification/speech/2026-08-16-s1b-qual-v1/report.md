# Speech Qualification Report — 2026-08-16-s1b-qual-v1

- Dataset version: `speech-qual-2026-08-16-v1`
- Normalizer ruleset version: `builtin-v1`
- Vocabulary version: `builtin`

## ASR metrics

```json
{
  "empty_count": 0,
  "empty_transcript_rate": 0.0,
  "evaluated_count": 27,
  "failed_count": 0,
  "false_correction_count": 0,
  "false_correction_rate": 0.0,
  "latency_ms_p50": 702.0,
  "latency_ms_p95": 859.7,
  "non_empty_transcript_rate": 1.0,
  "normalization_improvement": 0.0,
  "normalized_aviation_term_accuracy": 0.6111,
  "normalized_text_similarity": 0.865,
  "raw_aviation_term_accuracy": 0.6111,
  "raw_text_similarity": 0.865,
  "request_success_rate": 1.0,
  "retry_rate": 0.0,
  "review_required_rate": 0.0,
  "skipped_count": 5,
  "success_count": 27,
  "terminal_failure_rate": 0.0
}
```

## TTS metrics

```json
{
  "api_success_rate": 1.0,
  "empty_audio_count": 0,
  "empty_audio_rate": 0.0,
  "evaluated_count": 10,
  "failed_count": 0,
  "failure_rate": 0.0,
  "latency_ms_p50": 1608.5,
  "latency_ms_p95": 2799.5999999999985,
  "retry_rate": 0.0,
  "round_trip_norm_similarity": 0.896,
  "round_trip_raw_similarity": 0.8833,
  "round_trip_term_accuracy": 0.7167,
  "skipped_count": 0,
  "success_count": 10,
  "valid_audio_rate": 1.0
}
```

## Not-evaluated / failed cases

- `asr-h1` SKIPPED: human audio dir not provided
- `asr-h2` SKIPPED: human audio dir not provided
- `asr-h3` SKIPPED: human audio dir not provided
- `asr-h4` SKIPPED: human audio dir not provided
- `asr-h5` SKIPPED: human audio dir not provided
