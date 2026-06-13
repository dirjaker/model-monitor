.PHONY: install run-proxy run-sniffer run-web run-tui clean test lint

install:
	pip install -r requirements.txt

run-proxy:
	python main.py proxy

run-sniffer:
	python main.py sniffer

run-web:
	python main.py web

run-tui:
	python main.py tui

stats:
	python main.py stats

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ .mypy_cache/ .pytest_cache/ .ruff_cache/

lint:
	python -m py_compile main.py
	@for f in src/*.py src/**/*.py; do python -m py_compile "$$f" && echo "OK: $$f"; done

# macOS 打包
app:
	python packaging/py2app_setup.py py2app

# 初始化 git 仓库
init-git:
	git init
	git checkout -b dev
	git add .
	git commit -m "Initial commit: unified model-monitor project"
