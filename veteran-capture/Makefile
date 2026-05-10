.PHONY: help venv install install-dev fmt lint typecheck test smoke clean

PY := python3.13
VENV := .venv
PIP := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy

help:
	@echo "Targets:"
	@echo "  venv         create local virtualenv with python3.13"
	@echo "  install      install runtime dependencies"
	@echo "  install-dev  install runtime + dev dependencies (editable)"
	@echo "  fmt          run ruff formatter"
	@echo "  lint         run ruff linter"
	@echo "  typecheck    run mypy"
	@echo "  test         run pytest"
	@echo "  smoke        verify imports + settings load (no API calls)"
	@echo "  clean        remove venv and caches"

venv:
	$(PY) -m venv $(VENV)
	$(PIP) install --upgrade pip wheel

install: venv
	$(PIP) install -e .

install-dev: venv
	$(PIP) install -e ".[dev]"

fmt:
	$(RUFF) format src tests

lint:
	$(RUFF) check src tests

typecheck:
	$(MYPY) src

test:
	$(PYTEST)

smoke:
	$(PYTHON) -c "import veteran_capture; from veteran_capture.config import get_settings; from veteran_capture.logging_setup import configure_logging, get_logger; configure_logging(); get_logger('smoke').info('ok'); print('imports ok, version=' + veteran_capture.__version__)"

clean:
	rm -rf $(VENV) .ruff_cache .mypy_cache .pytest_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
