import os
from typing import Any, Dict, List, Optional

import yaml

_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _read_ini(path: str) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _flatten_paths(data: Any, prefix: str = "") -> List[str]:
    if not isinstance(data, dict):
        return []
    paths: List[str] = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        paths.append(path)
        paths.extend(_flatten_paths(value, path))
    return paths


def _get_by_path(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _set_by_path(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = data
    for key in parts[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[parts[-1]] = value


def load_config(path: str = "") -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and not path:
        return _CONFIG_CACHE

    cfg: Dict[str, Any] = {}
    candidate_paths = [path] if path else ["config.yaml", "config.yml", "config.ini"]
    target = next((p for p in candidate_paths if p and os.path.exists(p)), "")

    if target:
        if target.endswith((".yaml", ".yml")):
            cfg = _read_yaml(target)
        else:
            cfg = _read_ini(target)

    # 环境变量覆盖，支持嵌套键：ai.platform -> AI_PLATFORM
    for path_key in _flatten_paths(cfg):
        env_name = path_key.upper().replace(".", "_")
        env_val = os.getenv(env_name)
        if env_val is not None:
            _set_by_path(cfg, path_key, env_val)

    if not path:
        _CONFIG_CACHE = cfg
    return cfg


def get_config_value(key: str, default: str = "") -> str:
    cfg: Dict[str, Any] = {}
    try:
        cfg = load_config()
    except Exception as e:
        print(f"加载配置文件失败: {e}")

    env_val = os.getenv(key.upper().replace(".", "_"))
    if env_val is not None:
        return env_val

    value = _get_by_path(cfg, key)
    if value is None and "." not in key and "_" in key:
        # 兼容旧形式 ai_platform -> ai.platform
        prefix, rest = key.split("_", 1)
        value = _get_by_path(cfg, f"{prefix}.{rest}")

    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return default
    return str(value)


def get_config_bool(key: str, default: bool = False) -> bool:
    cfg = load_config()
    value = _get_by_path(cfg, key)
    if value is None and "." not in key and "_" in key:
        prefix, rest = key.split("_", 1)
        value = _get_by_path(cfg, f"{prefix}.{rest}")
    if isinstance(value, bool):
        return value
    raw = get_config_value(key, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def get_config_section(key: str) -> Dict[str, Any]:
    cfg = load_config()
    value = _get_by_path(cfg, key)
    return value if isinstance(value, dict) else {}


def get_config_list(key: str) -> List[Any]:
    cfg = load_config()
    value = _get_by_path(cfg, key)
    return value if isinstance(value, list) else []


def get_prefixed_config(prefix: str) -> Dict[str, str]:
    cfg = load_config()
    value = _get_by_path(cfg, prefix)
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if not isinstance(v, (dict, list))}

    data: Dict[str, str] = {}
    if isinstance(cfg, dict):
        start = f"{prefix}_"
        for key, item in cfg.items():
            if key.startswith(start):
                data[key[len(start):]] = str(item)
    return data
