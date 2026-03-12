import json
import re
from typing import Any, Dict

import requests
from openai import OpenAI

from utils.config import get_config_bool, get_config_section, get_config_value


def _extract_json(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except Exception:
            pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def _normalize_ai_payload(payload: Dict[str, Any], fallback: str = "") -> Dict[str, Any]:
    suggestions = payload.get("suggestions", [])
    if isinstance(suggestions, str):
        suggestions = [i.strip() for i in suggestions.split("\n") if i.strip()]
    if not isinstance(suggestions, list):
        suggestions = []

    conclusion = str(payload.get("conclusion", "")).strip()
    if not conclusion:
        conclusion = fallback.strip().splitlines()[0] if fallback.strip() else "未能生成明确结论"

    return {
        "conclusion": conclusion,
        "risk_level": str(payload.get("risk_level", "UNKNOWN")).upper(),
        "analysis": str(payload.get("analysis", "")).strip(),
        "suggestions": [str(i).strip() for i in suggestions if str(i).strip()],
    }


def is_ai_enabled() -> bool:
    ai = get_config_section("ai")
    enabled = ai.get("enabled", get_config_bool("ai_enabled", True))
    if not isinstance(enabled, bool):
        enabled = str(enabled).strip().lower() in {"1", "true", "yes", "y", "on"}
    platform = str(ai.get("platform", "")).strip().lower()
    has_base = bool(enabled and ai.get("platform") and ai.get("url") and ai.get("model"))
    if not has_base:
        return False
    if platform in {"ollama", "ollma"}:
        return True
    return bool(ai.get("key"))


def _analyze_with_ollama(url: str, model: str, system_prompt: str, prompt: str) -> Dict[str, Any]:
    base_url = url.rstrip("/")
    endpoint = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    resp = requests.post(endpoint, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    content = (
        (data.get("message") or {}).get("content")
        or data.get("response")
        or ""
    )
    parsed = _extract_json(content)
    normalized = _normalize_ai_payload(payload=parsed, fallback=content)
    return {"success": True, "provider": "ollama", "raw_response": content, **normalized}


def analyze_inspection_result(inspection_result: str) -> Dict[str, Any]:
    ai = get_config_section("ai")
    provider = str(ai.get("platform", get_config_value("ai_platform", ""))).strip()
    url = str(ai.get("url", get_config_value("ai_url", ""))).strip()
    key = str(ai.get("key", get_config_value("ai_key", ""))).strip()
    model = str(ai.get("model", get_config_value("ai_model", ""))).strip()
    provider_lc = provider.lower()
    system_prompt = str(
        ai.get(
            "system_prompt",
            get_config_value(
                "ai_system_prompt",
                "你是资深网络运维巡检分析助手。请给出明确结论和可执行建议。",
            ),
        )
    ).strip()

    if not (provider and url and model):
        return {"success": False, "error": "AI 配置不完整，请检查 ai_platform/ai_url/ai_model"}
    if provider_lc not in {"ollama", "ollma"} and not key:
        return {"success": False, "error": "AI 配置不完整，请检查 ai_key"}

    prompt = (
        "请分析以下网络设备巡检结果，只返回 JSON，且不要输出额外文字。JSON 结构:\n"
        '{\n'
        '  "conclusion": "一句话结论",\n'
        '  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",\n'
        '  "analysis": "详细分析",\n'
        '  "suggestions": ["建议1", "建议2"]\n'
        '}\n'
        f"巡检内容如下:\n{inspection_result}"
    )

    try:
        if provider_lc in {"ollama", "ollma"}:
            return _analyze_with_ollama(url=url, model=model, system_prompt=system_prompt, prompt=prompt)

        client = OpenAI(api_key=key, base_url=url)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        content = completion.choices[0].message.content or ""
        payload = _extract_json(content)
        normalized = _normalize_ai_payload(payload=payload, fallback=content)
        return {"success": True, "provider": provider, "raw_response": content, **normalized}
    except Exception as e:
        return {"success": False, "provider": provider, "error": f"AI 调用失败: {e}"}
