"""
测试配置模块

测试 YAML 配置加载、默认值、环境变量覆盖。
"""

import os
import tempfile

import pytest
import yaml

from src.config import Config, _resolve_env_vars, _apply_env_overrides


SAMPLE_CONFIG = """
mode: proxy
proxy:
  host: 0.0.0.0
  port: 8080
  timeout: 120
sniffer:
  port: 8080
  targets:
    - api.deepseek.com
web:
  host: 127.0.0.1
  port: 8000
database:
  path: data/usage.db
providers:
  deepseek:
    base_url: https://api.deepseek.com
    api_key: sk-test-key
    pricing:
      deepseek-chat:
        input: 1.0
        output: 2.0
alerts:
  enabled: false
  daily_threshold: 10.0
  monthly_threshold: 200.0
"""


@pytest.fixture
def config_file():
    """创建临时配置文件"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
    tmp.write(SAMPLE_CONFIG)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


class TestConfig:
    """配置加载和查询测试"""

    def test_load_config(self, config_file):
        """应正确加载 YAML 配置"""
        config = Config(config_file)
        assert config.mode == "proxy"
        assert config.proxy_host == "0.0.0.0"
        assert config.proxy_port == 8080
        assert config.proxy_timeout == 120
        assert config.web_host == "127.0.0.1"
        assert config.web_port == 8000
        assert config.db_path == "data/usage.db"

    def test_alerts_config(self, config_file):
        """应正确读取告警配置"""
        config = Config(config_file)
        assert config.alerts_enabled is False
        assert config.alerts_daily_threshold == 10.0
        assert config.alerts_monthly_threshold == 200.0
        assert config.alerts_webhook_url == ""

    def test_get_with_default(self, config_file):
        """不存在的键应返回默认值"""
        config = Config(config_file)
        assert config.get("nonexistent.key", "default") == "default"
        assert config.get("nonexistent", 42) == 42

    def test_set_and_save(self, config_file):
        """设置并保存配置"""
        config = Config(config_file)
        config.set("proxy.port", 9090)
        config.save()

        # 重新加载验证
        config2 = Config(config_file)
        assert config2.proxy_port == 9090

    def test_default_config(self):
        """无配置文件时应使用默认值"""
        config = Config("/nonexistent/path/config.yaml")
        assert config.mode == "proxy"
        assert config.proxy_host == "0.0.0.0"
        assert config.proxy_port == 8080
        assert config.web_host == "0.0.0.0"
        assert config.web_port == 8000

    def test_env_var_resolution(self):
        """环境变量引用应被解析"""
        os.environ["MM_TEST_KEY"] = "test_value_42"
        data = _resolve_env_vars({"key": "${MM_TEST_KEY}"})
        assert data["key"] == "test_value_42"
        del os.environ["MM_TEST_KEY"]

    def test_env_var_resolution_nested(self):
        """嵌套字典中的环境变量也应被解析"""
        os.environ["MM_API_KEY"] = "sk-1234"
        data = _resolve_env_vars({"provider": {"api_key": "${MM_API_KEY}"}})
        assert data["provider"]["api_key"] == "sk-1234"
        del os.environ["MM_API_KEY"]

    def test_env_var_resolution_list(self):
        """列表中的环境变量也应被解析"""
        os.environ["MM_HOST"] = "api.example.com"
        data = _resolve_env_vars({"targets": ["${MM_HOST}", "fallback.com"]})
        assert data["targets"][0] == "api.example.com"
        assert data["targets"][1] == "fallback.com"
        del os.environ["MM_HOST"]

    def test_env_override(self, config_file):
        """环境变量覆盖应生效"""
        os.environ["MM_PROXY_PORT"] = "9090"
        config = Config(config_file)
        assert config.proxy_port == 9090
        del os.environ["MM_PROXY_PORT"]

    def test_env_override_bool(self, config_file):
        """环境变量布尔值覆盖"""
        os.environ["MM_ALERTS_ENABLED"] = "true"
        config = Config(config_file)
        assert config.alerts_enabled is True
        del os.environ["MM_ALERTS_ENABLED"]

    def test_sniffer_config(self, config_file):
        """嗅探器配置"""
        config = Config(config_file)
        assert config.sniffer_port == 8080
        assert config.sniffer_targets == ["api.deepseek.com"]

    def test_repr(self, config_file):
        """__repr__ 应包含路径和模式"""
        config = Config(config_file)
        rep = repr(config)
        assert "proxy" in rep
        assert config_file in rep
