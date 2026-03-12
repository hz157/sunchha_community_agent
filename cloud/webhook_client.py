from typing import Any, Dict, List

import requests

from utils.config import get_config_bool, get_config_list, get_config_section


def _payload(platform: str, text: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    p = platform.lower()
    if p == "telegram":
        return {"chat_id": cfg.get("key") or cfg.get("appid"), "text": text}
    if p == "dingding":
        return {"msgtype": "text", "text": {"content": text}}
    if p == "wechat":
        return {"msgtype": "text", "text": {"content": text}}
    if p in {"feishu", "lark"}:
        return {"msg_type": "text", "content": {"text": text}}
    return {"text": text}


def _send(cfg: Dict[str, Any], text: str) -> Dict[str, Any]:
    platform = str(cfg.get("platform", "")).strip()
    url = str(cfg.get("url", "")).strip()
    if not platform or not url:
        return {"provider": platform or "unknown", "success": False, "error": "缺少 platform 或 url"}

    try:
        resp = requests.post(
            url,
            json=_payload(platform, text=text, cfg=cfg),
            timeout=15,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            return {"provider": platform, "success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        return {"provider": platform, "success": True}
    except Exception as e:
        return {"provider": platform, "success": False, "error": str(e)}


def _build_message(result: Dict[str, Any]) -> str:
    ai_info = result.get("ai_analysis") or {}
    return (
        "Sunchha 巡检完成\n"
        f"IP: {result.get('ip')}\n"
        f"协议: {result.get('protocol')}\n"
        f"结果: {result.get('status')}\n"
        f"AI结论: {ai_info.get('conclusion', '未生成')}"
    )


def notify_inspection_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    webhook = get_config_section("webhook")
    enabled = webhook.get("enabled", get_config_bool("webhook_enabled", False))
    if not isinstance(enabled, bool):
        enabled = str(enabled).strip().lower() in {"1", "true", "yes", "y", "on"}
    if not enabled:
        return []

    targets = get_config_list("webhook.targets")
    if not targets:
        return []

    text = _build_message(result)
    responses: List[Dict[str, Any]] = []
    for item in targets:
        if isinstance(item, dict):
            responses.append(_send(item, text))
    return responses
