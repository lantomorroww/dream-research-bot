.PHONY: help install install-dev test run clean

help:
	@echo "Доступные команды:"
	@echo "  make install      — установить пакет и зависимости"
	@echo "  make install-dev  — установить + dev-зависимости (pytest)"
	@echo "  make test         — запустить тесты"
	@echo "  make run          — запустить бота (требует .env)"
	@echo "  make clean        — удалить кэши и артефакты сборки"

install:
	python3 -m pip install --upgrade pip
	python3 -m pip install -e .

install-dev:
	python3 -m pip install --upgrade pip
	python3 -m pip install -e ".[dev]"

test:
	python3 -m pytest -v

run:
	python3 main.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/
