"""Sprint 1B Speech remediation regression coverage.

Verifies: builtin-v2 normalizer high-confidence rules apply and low-confidence candidates
only warn (never silently rewrite), builtin-v1 behavior is preserved, the configurable TTS
pronunciation prompt reaches the provider payload, and the real-human manifest loader is
safe (filters placeholder audio, keeps gold text + hashes, never loads audio into git).
"""

from __future__ import annotations

import asyncio
import io
import json
import wave

from app.ai.providers.speech.mimo_tts import MiMoTTSProvider
from app.core.config import Settings
from app.normalization.normalizer import NORMALIZER_RULESET_VERSION, normalize
from app.normalization.vocabulary import VocabularySnapshot
from scripts.speech_qualification.run import load_human_cases, spell_out_aviation

VOCAB = VocabularySnapshot(version="builtin")


def test_builtin_v2_applies_high_confidence_aviation_rules() -> None:
    cases = [
        ("该B-737NG飞机已完成检修。", "B737NG"),
        ("B七三七负八百的发动机需要更换。", "B737-800"),
        ("该CFM56七字节发动机已更换叶片。", "CFM56-7B"),
        ("试航指令已评估执行。", "适航指令"),
        ("对低设备清单由运行部门维护。", "最低设备清单"),
        ("根据 M E L 评估后执行故障保留。", "MEL"),
        ("需要查询 A M M 和 F I M。", "AMM"),
        ("执行 M P D 检查项目。", "MPD"),
    ]
    for raw, expected in cases:
        result = normalize(raw, VOCAB, ruleset_version=NORMALIZER_RULESET_VERSION)
        assert expected in result.normalized_text, f"{raw!r} should contain {expected}"
        assert result.ruleset_version == NORMALIZER_RULESET_VERSION


def test_builtin_v2_low_confidence_candidates_warn_without_rewriting() -> None:
    candidates = [
        ("根据四百五十评估后执行故障保留。", "CDL"),
        ("执行NPD检查项目。", "MPD"),
        ("完成E U后签署维修记录。", "EO"),
        ("该Swiflam五六发动机参数正常。", "CFM56"),
        ("根据ML放行并记录故障保留。", "MEL"),
    ]
    for raw, term in candidates:
        result = normalize(raw, VOCAB, ruleset_version=NORMALIZER_RULESET_VERSION)
        # The candidate is NOT silently rewritten to the aviation term...
        assert term not in result.normalized_text
        # ...but it IS flagged for review.
        assert result.warnings, f"expected a review warning for {raw!r}"


def test_builtin_v2_never_rewrites_plain_text_into_abbreviation_without_context() -> None:
    # A bare, out-of-context occurrence must not be replaced (dangerous-replacement guard).
    result = normalize("今天是四百五十号文件的修订。", VOCAB, ruleset_version=NORMALIZER_RULESET_VERSION)
    assert "四百五十" in result.normalized_text
    assert "CDL" not in result.normalized_text
    # No hint context -> no warning either.
    assert result.warnings == ()


def test_builtin_v1_ruleset_behavior_is_preserved() -> None:
    result = normalize("B七三七NG 维修放心", VOCAB, ruleset_version="builtin-v1")
    assert result.normalized_text == "B737NG 维修放行"
    assert result.ruleset_version == "builtin-v1"
    # v1 has no spaced-abbreviation or v2 typed-variant rules.
    old = normalize("根据 M E L 评估", VOCAB, ruleset_version="builtin-v1")
    assert "M E L" in old.normalized_text
    new = normalize("根据 M E L 评估", VOCAB, ruleset_version="builtin-v2")
    assert "MEL" in new.normalized_text


def test_tts_style_prompt_is_configurable_and_reaches_payload(tmp_path) -> None:
    captured: list[dict] = []

    async def fake_post(payload):
        captured.append(payload)
        return {"choices": [{"message": {"audio": {"data": "QUFBQQ=="}}}]}, "req"

    provider = MiMoTTSProvider(
        "https://base", "key", "mimo-v2.5-tts",
        style_prompt="请逐字母清晰读出缩写。",
    )
    provider._post = fake_post
    import asyncio

    asyncio.run(provider.synthesize("请说明 MEL 的作用。"))
    assert captured[0]["messages"][0]["content"] == "请逐字母清晰读出缩写。"

    settings = Settings(_env_file=None)
    assert settings.mimo_tts_style_prompt.startswith("请使用清晰")


def test_human_manifest_loader_filters_placeholder_and_keeps_gold(tmp_path) -> None:
    manifest = [
        {
            "speaker_alias": "S01",
            "case_id": "case01",
            "condition": "NORMAL",
            "expected_text": "请说明 MEL 的作用，以及故障保留的基本要求。",
            "filename": "S01_case01.wav",
            "sha256": "a" * 64,
            "size_bytes": 191084,
        },
        {
            "speaker_alias": "S02",
            "case_id": "case01",
            "expected_text": "请说明 MEL 的作用。",
            "filename": "S02_case01.wav",
            "sha256": "b" * 64,
            "size_bytes": 44,  # placeholder -> must be filtered
        },
    ]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    cases = load_human_cases(path)
    assert len(cases) == 1
    case = cases[0]
    assert case["case_id"] == "S01-case01"
    assert case["audio_filename"] == "S01_case01.wav"
    assert "MEL" in case["expected_terms"] and "故障保留" in case["expected_terms"]
    assert case["source"] == "human"


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000)
    return buffer.getvalue()


def test_s01_gate_offline_writes_remediation_artifacts(tmp_path) -> None:
    from scripts.speech_qualification.run import run_s01_gate

    manifest = [
        {
            "speaker_alias": "S01",
            "case_id": f"case0{i}",
            "condition": "NORMAL",
            "expected_text": "请说明 MEL 的作用。",
            "filename": f"S01_case0{i}.wav",
            "sha256": "a" * 64,
            "size_bytes": 16044,
        }
        for i in (1, 2)
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    for i in (1, 2):
        (audio_dir / f"S01_case0{i}.wav").write_bytes(_wav_bytes())

    settings = Settings(_env_file=None)
    output = asyncio.run(
        run_s01_gate(
            run_id="s01-offline",
            output_dir=tmp_path / "out",
            settings=settings,
            human_manifest=manifest_path,
            audio_dir=audio_dir,
            provider_kind="fake",
            max_retries=0,
        )
    )
    files = {p.name for p in output.iterdir()}
    assert {
        "manifest.json",
        "results.json",
        "metrics.json",
        "failures.json",
        "normalization-errors.json",
        "remediation.json",
        "s01-manifest.json",
        "report.md",
    } <= files
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert "asr_raw" in metrics
    assert "asr_normalized_v1" in metrics and "asr_normalized_v2" in metrics
    assert "tts_before" in metrics and "tts_prompt_after" in metrics
    remediation = json.loads((output / "remediation.json").read_text(encoding="utf-8"))
    assert "normalizer_delta" in remediation and "tts_pronunciation_after" in remediation


def test_spell_out_aviation_expands_abbreviations() -> None:
    assert spell_out_aviation("根据 MEL 评估后执行故障保留。") == "根据 M E L 评估后执行故障保留。"
    assert spell_out_aviation("查询 AMM 和 FIM。") == "查询 A M M 和 F I M。"
    assert spell_out_aviation("B737NG 起落架检查完毕。") == "B737NG 起落架检查完毕。"  # model untouched


def test_builtin_v3_human_speech_phrase_rules_apply() -> None:
    result = normalize("发现失航指令适用时，应确认AD的执行状态。", VOCAB, ruleset_version="builtin-v3")
    assert "适航指令" in result.normalized_text
    assert "失航指令" not in result.normalized_text
    result2 = normalize("该飞机为B-737-800，发动机型号为CF56-7B。", VOCAB, ruleset_version="builtin-v3")
    assert "B737-800" in result2.normalized_text
    # CF56-7B is a review-only candidate: not silently rewritten, but flagged.
    assert "CFM56-7B" not in result2.normalized_text
    assert any("CF56-7B" in w for w in result2.warnings)


def test_recompute_normalizations_from_cached_raw(tmp_path) -> None:
    from scripts.speech_qualification.run import recompute_normalizations

    result = {
        "status": "SUCCESS",
        "raw_transcript": "B七三七NG飞机完成维修后，应该如何进行维修放行？",
        "gold_text": "B737NG 飞机完成维修后，应如何进行维修放行？",
        "expected_terms": ["B737NG", "维修放行"],
    }
    updated = recompute_normalizations(result, ("builtin-v1", "builtin-v2", "builtin-v3"))
    assert "builtin-v3" in updated["normalizations"]
    assert "B737NG" in updated["normalizations"]["builtin-v3"]["normalized_text"]
    assert updated["normalizations"]["builtin-v3"]["norm_term_accuracy"] == 1.0
    assert updated["normalizations"]["builtin-v3"]["false_corrections"] == []
