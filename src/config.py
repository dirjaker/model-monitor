"""
统一配置管理模块
从 YAML 文件加载配置，支持环境变量覆盖。
环境变量格式: MM_<SECTION>_<KEY>，例如 MM_PROXY_PORT=9090
"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config.yaml"


def _resolve_env_vars(value: Any) -> Any:
    """递归解析字符串中的环境变量引用 ${VAR_NAME}"""
    if isinstance(value, str):
        pattern = re.compile(r"\$\{(\w+)\}")
        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, "")
        return pattern.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """
    应用环境变量覆盖。
    格式: MM_<SECTION>_<KEY>=value
    例如: MM_PROXY_PORT=9090 覆盖 config["proxy"]["port"]
    """
    prefix = "MM_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix):].lower().split("_", 1)
        if len(parts) == 2:
            section, param = parts
            if section in config and isinstance(config[section], dict):
                # 尝试转换类型
                converted: Any = value
                if param in config[section]:
                    orig_type = type(config[section][param])
                    if orig_type is int:
                        try:
                            converted = int(value)
                        except ValueError:
                            pass
                    elif orig_type is float:
                        try:
                            converted = float(value)
                        except ValueError:
                            pass
                    elif orig_type is bool:
                        converted = value.lower() in ("true", "1", "yes")
                config[section][param] = converted
                logger.debug("环境变量覆盖: %s -> %s.%s = %s", key, section, param, converted)
    return config


def _merge_dicts(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 优先"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """统一配置管理器"""

    def __init__(self, config_path: Optional[str] = None):
        self._data: dict[str, Any] = {}
        self._path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self.load()

    def load(self) -> None:
        """加载配置文件"""
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            self._data = _resolve_env_vars(raw)
            self._data = _apply_env_overrides(self._data)
            logger.info("配置已加载: %s", self._path)
        else:
            logger.warning("配置文件不存在，使用默认值: %s", self._path)
            self._data = self._defaults()

    def _defaults(self) -> dict[str, Any]:
        return {
            "mode": "proxy",
            "proxy": {"host": "127.0.0.1", "port": 12345, "timeout": 120},
            "sniffer": {"port": 8080, "targets": ["api.deepseek.com", "openrouter.ai"]},
            "web": {"host": "0.0.0.0", "port": 8000},
            "database": {"path": "data/usage.db"},
            "providers": {},
            "alerts": {"enabled": False, "daily_threshold": 10.0, "monthly_threshold": 200.0, "webhook_url": ""},
        }

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的路径"""
        parts = key.split(".")
        current: Any = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def save(self) -> None:
        """保存配置到文件"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("配置已保存: %s", self._path)

    @property
    def mode(self) -> str:
        return str(self._data.get("mode", "proxy"))

    @property
    def proxy_host(self) -> str:
        return str(self.get("proxy.host", "127.0.0.1"))

    @property
    def proxy_port(self) -> int:
        return int(self.get("proxy.port", 12345))

    @property
    def proxy_timeout(self) -> int:
        return int(self.get("proxy.timeout", 120))

    @property
    def sniffer_port(self) -> int:
        return int(self.get("sniffer.port", 8080))

    @property
    def sniffer_targets(self) -> list[str]:
        return list(self.get("sniffer.targets", []))

    @property
    def web_host(self) -> str:
        return str(self.get("web.host", "0.0.0.0"))

    @property
    def web_port(self) -> int:
        return int(self.get("web.port", 8000))

    @property
    def db_path(self) -> str:
        path = str(self.get("database.path", "data/usage.db"))
        # 确保目录存在
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def providers(self) -> dict[str, Any]:
        return dict(self._data.get("providers", {}))

    @property
    def alerts_enabled(self) -> bool:
        return bool(self.get("alerts.enabled", False))

    @property
    def alerts_daily_threshold(self) -> float:
        return float(self.get("alerts.daily_threshold", 10.0))

    @property
    def alerts_monthly_threshold(self) -> float:
        return float(self.get("alerts.monthly_threshold", 200.0))

    @property
    def alerts_webhook_url(self) -> str:
        return str(self.get("alerts.webhook_url", ""))

    def __repr__(self) -> str:
        return f"Config(path={self._path}, mode={self.mode})"
