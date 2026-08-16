"""Versioned Golden Dataset manifest for the Sprint 1B Speech Qualification Gate.

Audio itself is never committed: each case references its gold text, expected aviation
terminology, category and source type. Runtime audio hashes + metadata are recorded in the
generated artifacts (docs/qualification/qualification-history.md §3 format).
"""

from __future__ import annotations

from typing import Any

DATASET_VERSION = "speech-qual-2026-08-16-v1"
NORMALIZER_RULESET_VERSION = "builtin-v1"
VOCABULARY_VERSION = "builtin"  # no published business vocabulary at qualification time


def _asr_case(
    case_id: str,
    text: str,
    expected_terms: list[str],
    category: str,
    *,
    source: str = "tts",
    condition: str = "normal",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "category": category,
        "source": source,
        "condition": condition,
        "text": text,
        "expected_terms": expected_terms,
    }


ASR_CASES: list[dict[str, Any]] = [
    # A. 普通中文维修语句
    _asr_case("asr-01", "请说明维修工作完成后的放行流程。", ["维修", "放行"], "A_plain_chinese"),
    _asr_case("asr-02", "检查起落架系统是否存在渗漏。", ["起落架"], "A_plain_chinese"),
    _asr_case("asr-03", "按照工作单完成全部签署并归档。", ["工作单", "签署"], "A_plain_chinese"),
    # B. 航空英文缩写
    _asr_case("asr-04", "根据 MEL 评估后执行故障保留。", ["MEL", "故障保留"], "B_abbreviations"),
    _asr_case("asr-05", "需要查询 AMM 和 FIM。", ["AMM", "FIM"], "B_abbreviations"),
    _asr_case("asr-06", "该故障属于 CDL 项目。", ["CDL"], "B_abbreviations"),
    _asr_case("asr-07", "按 TSM 排故流程处理。", ["TSM"], "B_abbreviations"),
    _asr_case("asr-08", "参考 IPC 查找件号。", ["IPC"], "B_abbreviations"),
    _asr_case("asr-09", "执行 MPD 检查项目。", ["MPD"], "B_abbreviations"),
    _asr_case("asr-10", "按 AD 和 SB 评估。", ["AD", "SB"], "B_abbreviations"),
    _asr_case("asr-11", "完成 EO 后签署维修记录。", ["EO", "维修记录"], "B_abbreviations"),
    _asr_case("asr-12", "该机具备 ETOPS 放行资格。", ["ETOPS"], "B_abbreviations"),
    _asr_case("asr-13", "检查 APU 引气系统。", ["APU"], "B_abbreviations"),
    # C. 机型 / 发动机
    _asr_case("asr-14", "该 B737NG 飞机已完成检修。", ["B737NG"], "C_aircraft_engine"),
    _asr_case("asr-15", "B737-800 的发动机需要更换。", ["B737-800"], "C_aircraft_engine"),
    _asr_case("asr-16", "A330 起落架系统检查完毕。", ["A330"], "C_aircraft_engine"),
    _asr_case("asr-17", "CFM56 发动机参数正常。", ["CFM56"], "C_aircraft_engine"),
    _asr_case("asr-18", "该 CFM56-7B 发动机已更换叶片。", ["CFM56-7B"], "C_aircraft_engine"),
    # D. 中文维修专业术语
    _asr_case("asr-19", "放行人员核对维修放行条件。", ["放行人员", "维修放行"], "D_chinese_terms"),
    _asr_case("asr-20", "故障保留需经批准并记录。", ["故障保留"], "D_chinese_terms"),
    _asr_case("asr-21", "适航指令已评估执行。", ["适航指令"], "D_chinese_terms"),
    _asr_case("asr-22", "最低设备清单由运行部门维护。", ["最低设备清单"], "D_chinese_terms"),
    _asr_case("asr-23", "维修方案经工程部门批准。", ["维修方案"], "D_chinese_terms"),
    _asr_case("asr-24", "工程指令已下发执行。", ["工程指令"], "D_chinese_terms"),
    # E. 混合中英文口语
    _asr_case("asr-25", "根据 MEL 放行，并记录故障保留。", ["MEL", "故障保留"], "E_mixed"),
    _asr_case("asr-26", "需要查询 AMM 和 FIM 确认步骤。", ["AMM", "FIM"], "E_mixed"),
    _asr_case("asr-27", "该 CFM56-7B 发动机振动值正常。", ["CFM56-7B"], "E_mixed"),
    # F. 真人语音条件（需要外部 --audio-dir 提供音频；无音频则记录 not_evaluated）
    _asr_case("asr-h1", "请说明维修放行前需要核对哪些记录。", ["维修放行", "维修记录"], "F_human", source="human", condition="normal"),
    _asr_case("asr-h2", "根据 MEL 评估后执行故障保留。", ["MEL", "故障保留"], "F_human", source="human", condition="fast"),
    _asr_case("asr-h3", "需要查询 AMM 和 FIM。", ["AMM", "FIM"], "F_human", source="human", condition="paused"),
    _asr_case("asr-h4", "该 CFM56-7B 发动机参数正常。", ["CFM56-7B"], "F_human", source="human", condition="accent"),
    _asr_case("asr-h5", "B737NG 起落架检查完毕。", ["B737NG", "起落架"], "F_human", source="human", condition="noise"),
]


TTS_CASES: list[dict[str, Any]] = [
    _asr_case("tts-01", "请说明维修放行的基本流程。", ["维修放行"], "TTS_plain"),
    _asr_case("tts-02", "根据 MEL 评估后执行故障保留。", ["MEL", "故障保留"], "TTS_abbreviations"),
    _asr_case("tts-03", "需要查询 AMM 和 FIM。", ["AMM", "FIM"], "TTS_abbreviations"),
    _asr_case("tts-04", "该 CFM56-7B 发动机需要更换。", ["CFM56-7B"], "TTS_aircraft_engine"),
    _asr_case("tts-05", "B737NG 与 A330 的起落架系统检查完毕。", ["B737NG", "A330"], "TTS_aircraft_engine"),
    _asr_case("tts-06", "执行 MPD 检查项目并签署维修记录。", ["MPD", "维修记录"], "TTS_mixed"),
    _asr_case("tts-07", "按 AD 和 SB 评估后完成 EO。", ["AD", "SB", "EO"], "TTS_mixed"),
    _asr_case("tts-08", "ETOPS 放行前需检查 APU 引气系统。", ["ETOPS", "APU"], "TTS_mixed"),
    _asr_case(
        "tts-09",
        "请说明在完成例行维修工作后，放行人员应当如何核对维修记录、确认故障保留是否有效，并按照最低设备清单与适航指令的要求完成放行前检查。",
        ["放行人员", "维修记录", "故障保留", "最低设备清单", "适航指令", "放行"],
        "TTS_long",
    ),
    _asr_case("tts-10", "最低设备清单与维修方案由工程部门批准后执行。", ["最低设备清单", "维修方案"], "TTS_terms"),
]
