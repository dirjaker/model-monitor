#!/usr/bin/env python3
"""
模型监控工具 - 统一入口
合并代理模式与嗅探模式，提供统一的命令行界面。
"""

import sys
import os

# 确保项目根目录在 sys.path 中
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
