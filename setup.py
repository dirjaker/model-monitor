"""
py2app 打包配置
主要用于 macOS 应用打包，不影响 pip 安装。
"""

from setuptools import setup, find_packages

setup(
    name="model-monitor",
    version="1.0.0",
    description="Unified Model API Monitoring Tool",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="dirjaker",
    url="https://github.com/dirjaker/model-monitor",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.27",
        "fastapi>=0.115",
        "uvicorn>=0.34",
        "rich>=13.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "sniffer": ["mitmproxy>=10.0"],
        "macos": ["rumps>=0.4.0", "py2app>=0.28"],
        "all": ["mitmproxy>=10.0", "rumps>=0.4.0", "py2app>=0.28"],
    },
    entry_points={
        "console_scripts": [
            "model-monitor=src.cli:main",
        ],
    },
)
