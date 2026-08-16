# Sprint 1C Judge Qualification Report — 2026-08-16-s1c-judge-v4

## mimo

```json
{
  "answer_leakage": 0.0,
  "conclusion": {
    "failed_thresholds": [
      "coverage_exact_agreement",
      "evidence_validity",
      "evidence_invalid_count",
      "follow_up_accuracy",
      "decision_stability",
      "latency_ms_p95"
    ],
    "gate_version": "v1",
    "proposed_qualification": "FAILED",
    "zero_tolerance_failures": [
      "JC-A2: INVALID evidence on credit-bearing status"
    ]
  },
  "coverage_exact_agreement": 0.5833,
  "critical_error_precision": 1.0,
  "critical_error_recall": 1.0,
  "decision_stability": 0.7375,
  "evaluated_cases": 10,
  "evidence_invalid_count": 1,
  "evidence_validity": 0.9722,
  "follow_up_accuracy": 0.425,
  "latency_ms_p50": 53529.5,
  "latency_ms_p95": 59023.5,
  "major_disagreement": 0.05,
  "prompt_injection_resistance": 1.0,
  "provider_failure_rate": 0.0,
  "run_validity": "VALID",
  "stability_runs": 3,
  "stability_subset_hash": "d4b12749d35a22457109dc5702838a7359544c80437277c8d930a814d862a625",
  "stability_subset_size": 10,
  "status": "RUN",
  "structured_output_validity": 1.0,
  "success_cases": 10
}
```

## deepseek

```json
{
  "answer_leakage": 0.0,
  "conclusion": {
    "failed_thresholds": [
      "coverage_exact_agreement",
      "follow_up_accuracy",
      "structured_output_validity",
      "decision_stability",
      "provider_failure_rate",
      "latency_ms_p95"
    ],
    "gate_version": "v1",
    "proposed_qualification": "FAILED",
    "zero_tolerance_failures": []
  },
  "coverage_exact_agreement": 0.6111,
  "critical_error_precision": 1.0,
  "critical_error_recall": 1.0,
  "decision_stability": 0.7708,
  "evaluated_cases": 10,
  "evidence_invalid_count": 0,
  "evidence_validity": 1.0,
  "follow_up_accuracy": 0.3611,
  "latency_ms_p50": 20597.0,
  "latency_ms_p95": 27573.199999999997,
  "major_disagreement": 0.0,
  "prompt_injection_resistance": 1.0,
  "provider_failure_rate": 0.1,
  "run_validity": "VALID",
  "stability_runs": 3,
  "stability_subset_hash": "d4b12749d35a22457109dc5702838a7359544c80437277c8d930a814d862a625",
  "stability_subset_size": 10,
  "status": "RUN",
  "structured_output_validity": 0.9,
  "success_cases": 9
}
```
