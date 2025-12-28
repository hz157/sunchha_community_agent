import os
from typing import Dict


def load_config(path: str = "config.ini") -> Dict[str, str]:
    """
    轻量读取键值配置文件（不要求 section），并允许被环境变量覆盖。
    例如：community_api=https://...
    环境变量覆盖规则：将 key 转为大写作为 env 名，例如 COMMUNITY_API。
    """
    cfg: Dict[str, str] = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    key = k.strip()
                    val = v.strip()
                    cfg[key] = val
    except FileNotFoundError:
        # 配置文件可选，不存在则仅使用环境变量
        pass

    # 环境变量覆盖
    for k in list(cfg.keys()):
        env_name = k.upper()
        env_val = os.getenv(env_name)
        if env_val:
            cfg[k] = env_val

    return cfg


def get_config_value(key: str, default: str = "") -> str:
    try:
        cfg = load_config()
    except Exception as e:
        print(f"加载配置文件失败: {e}")
    return os.getenv(key.upper(), cfg.get(key, default))