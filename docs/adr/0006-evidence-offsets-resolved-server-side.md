# 0006. Evidence offset 服务端解析

> Status: ACCEPTED
> Date: 2026-08-16（Phase 0 Governance Baseline）
> Deciders: 评分与题库治理负责人

## Status

Accepted（固化自 `docs/SCORING.md` 与 `backend/app/scoring/evidence.py` 的既有实现）。

## Context

若依赖 LLM 计算 `start_char/end_char`，偏移常不可信且不可复现；必须由服务端以已采用转写为准解析。

## Decision

LLM 只返回 `quote`。服务端在已采用 transcript 上做精确匹配并计算偏移：

```text
0 match  → INVALID
1 match  → VALID
> 1 match → AMBIGUOUS
```

仅 `VALID` Evidence 可支持正式的 `covered / partial / TRIGGERED` 与 final point status。

## Alternatives

- 接受 LLM 提供的偏移（否决：不可信、不可复现）。

## Consequences

- 证据与转写严格绑定，可人工复核高亮。
- 无有效 span 的正式结论不得入库。

## Migration Impact

无（Phase 0 不改代码）。

## Testing Impact

测试：VALID/AMBIGUOUS/INVALID、跨 transcript span 拒绝（`docs/TESTING.md` Golden Dataset B/J）。
