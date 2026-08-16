# Speech Qualification Report — 2026-08-16-s1b-s01-qual-v3

## ASR RAW (S01 human)

```json
{
  "empty_transcript_rate": 0.0,
  "latency_ms_p50": 749.5,
  "latency_ms_p95": 884.3,
  "raw_aviation_term_accuracy": 0.525,
  "raw_text_similarity": 0.8897,
  "request_success_rate": 1.0,
  "retry_rate": 0.0,
  "terminal_failure_rate": 0.0
}
```

## asr_normalized_v1

```json
{
  "empty_count": 0,
  "empty_transcript_rate": 0.0,
  "evaluated_count": 10,
  "failed_count": 0,
  "false_correction_count": 0,
  "false_correction_rate": 0.0,
  "latency_ms_p50": 749.5,
  "latency_ms_p95": 884.3,
  "non_empty_transcript_rate": 1.0,
  "normalization_improvement": 0.025,
  "normalized_aviation_term_accuracy": 0.55,
  "normalized_text_similarity": 0.9017,
  "request_success_rate": 1.0,
  "retry_rate": 0.0,
  "review_required_rate": 0.1,
  "skipped_count": 0,
  "success_count": 10,
  "terminal_failure_rate": 0.0
}
```

## asr_normalized_v2

```json
{
  "empty_count": 0,
  "empty_transcript_rate": 0.0,
  "evaluated_count": 10,
  "failed_count": 0,
  "false_correction_count": 0,
  "false_correction_rate": 0.0,
  "latency_ms_p50": 749.5,
  "latency_ms_p95": 884.3,
  "non_empty_transcript_rate": 1.0,
  "normalization_improvement": 0.025,
  "normalized_aviation_term_accuracy": 0.55,
  "normalized_text_similarity": 0.9017,
  "request_success_rate": 1.0,
  "retry_rate": 0.0,
  "review_required_rate": 0.1,
  "skipped_count": 0,
  "success_count": 10,
  "terminal_failure_rate": 0.0
}
```

## asr_normalized_v3

```json
{
  "empty_count": 0,
  "empty_transcript_rate": 0.0,
  "evaluated_count": 10,
  "failed_count": 0,
  "false_correction_count": 0,
  "false_correction_rate": 0.0,
  "latency_ms_p50": 749.5,
  "latency_ms_p95": 884.3,
  "non_empty_transcript_rate": 1.0,
  "normalization_improvement": 0.1583,
  "normalized_aviation_term_accuracy": 0.6833,
  "normalized_text_similarity": 0.9196,
  "request_success_rate": 1.0,
  "retry_rate": 0.0,
  "review_required_rate": 0.5,
  "skipped_count": 0,
  "success_count": 10,
  "terminal_failure_rate": 0.0
}
```

## Normalizer remediation

```json
{
  "baseline": "builtin-v1",
  "false_correction_count_after": 0,
  "false_correction_count_before": 0,
  "final": "builtin-v3",
  "normalized_aviation_term_accuracy_after": 0.6833,
  "normalized_aviation_term_accuracy_before": 0.55,
  "normalized_aviation_term_accuracy_delta": 0.1333,
  "per_version": {
    "builtin-v1": {
      "empty_count": 0,
      "empty_transcript_rate": 0.0,
      "evaluated_count": 10,
      "failed_count": 0,
      "false_correction_count": 0,
      "false_correction_rate": 0.0,
      "latency_ms_p50": 749.5,
      "latency_ms_p95": 884.3,
      "non_empty_transcript_rate": 1.0,
      "normalization_improvement": 0.025,
      "normalized_aviation_term_accuracy": 0.55,
      "normalized_text_similarity": 0.9017,
      "raw_aviation_term_accuracy": 0.525,
      "raw_text_similarity": 0.8897,
      "request_success_rate": 1.0,
      "retry_rate": 0.0,
      "review_required_rate": 0.1,
      "skipped_count": 0,
      "success_count": 10,
      "terminal_failure_rate": 0.0
    },
    "builtin-v2": {
      "empty_count": 0,
      "empty_transcript_rate": 0.0,
      "evaluated_count": 10,
      "failed_count": 0,
      "false_correction_count": 0,
      "false_correction_rate": 0.0,
      "latency_ms_p50": 749.5,
      "latency_ms_p95": 884.3,
      "non_empty_transcript_rate": 1.0,
      "normalization_improvement": 0.025,
      "normalized_aviation_term_accuracy": 0.55,
      "normalized_text_similarity": 0.9017,
      "raw_aviation_term_accuracy": 0.525,
      "raw_text_similarity": 0.8897,
      "request_success_rate": 1.0,
      "retry_rate": 0.0,
      "review_required_rate": 0.1,
      "skipped_count": 0,
      "success_count": 10,
      "terminal_failure_rate": 0.0
    },
    "builtin-v3": {
      "empty_count": 0,
      "empty_transcript_rate": 0.0,
      "evaluated_count": 10,
      "failed_count": 0,
      "false_correction_count": 0,
      "false_correction_rate": 0.0,
      "latency_ms_p50": 749.5,
      "latency_ms_p95": 884.3,
      "non_empty_transcript_rate": 1.0,
      "normalization_improvement": 0.1583,
      "normalized_aviation_term_accuracy": 0.6833,
      "normalized_text_similarity": 0.9196,
      "raw_aviation_term_accuracy": 0.525,
      "raw_text_similarity": 0.8897,
      "request_success_rate": 1.0,
      "retry_rate": 0.0,
      "review_required_rate": 0.5,
      "skipped_count": 0,
      "success_count": 10,
      "terminal_failure_rate": 0.0
    }
  },
  "raw_vs_normalized_gap_final": 0.1583,
  "review_required_rate_after": 0.5,
  "review_required_rate_before": 0.1
}
```

## TTS before

```json
{
  "api_success_rate": 1.0,
  "empty_audio_count": 0,
  "empty_audio_rate": 0.0,
  "evaluated_count": 10,
  "failed_count": 0,
  "failure_rate": 0.0,
  "latency_ms_p50": 2640.0,
  "latency_ms_p95": 4713.65,
  "retry_rate": 0.0,
  "round_trip_norm_similarity": 0.8884,
  "round_trip_raw_similarity": 0.8757,
  "round_trip_term_accuracy": 0.75,
  "skipped_count": 0,
  "success_count": 10,
  "valid_audio_rate": 1.0
}
```

## tts_spellout_after

```json
{
  "api_success_rate": 1.0,
  "empty_audio_count": 0,
  "empty_audio_rate": 0.0,
  "evaluated_count": 10,
  "failed_count": 0,
  "failure_rate": 0.0,
  "latency_ms_p50": 2781.0,
  "latency_ms_p95": 4542.0999999999985,
  "retry_rate": 0.0,
  "round_trip_norm_similarity": 0.8647,
  "round_trip_raw_similarity": 0.8138,
  "round_trip_term_accuracy": 0.8,
  "skipped_count": 0,
  "success_count": 10,
  "valid_audio_rate": 1.0
}
```

## TTS pronunciation remediation

```json
{
  "round_trip_raw_similarity_after": 0.8138,
  "round_trip_raw_similarity_before": 0.8757,
  "round_trip_term_accuracy_delta": 0.05
}
```
