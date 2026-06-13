"""
py2app 打包脚本
用于生成 macOS .app 包。
用法: python packaging/py2app_setup.py py2app
"""

from setuptools import setup

APP = ["main.py"]
DATA_FILES = ["config.yaml"]
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "Model Monitor",
        "CFBundleDisplayName": "Model Monitor",
        "CFBundleIdentifier": "com.modelmonitor.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
        "LSUIElement": False,
    },
    "packages": ["src"],
    "includes": ["httpx", "fastapi", "uvicorn", "rich", "yaml", "mitmproxy"],
    "excludes": ["tkinter", "matplotlib", "numpy", "scipy"],
    "iconfile": "packaging/icon.icns",
}

setup(
    name="Model Monitor",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
