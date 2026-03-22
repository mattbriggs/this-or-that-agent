PYTHON ?= python3
PYTEST ?= pytest
COVERAGE_FILE ?= /tmp/tot-agent.coverage

.PHONY: install-dev lint test-unit test-integration coverage docs check

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check src tests

test-unit:
	$(PYTEST) --no-cov tests/unit

test-integration:
	RUN_INTEGRATION_TESTS=1 $(PYTEST) --no-cov tests/integration

coverage:
	COVERAGE_FILE=$(COVERAGE_FILE) coverage run -m pytest --no-cov tests/unit
	COVERAGE_FILE=$(COVERAGE_FILE) coverage report -m
	COVERAGE_FILE=$(COVERAGE_FILE) coverage html
	COVERAGE_FILE=$(COVERAGE_FILE) coverage json

docs:
	mkdocs build

check:
	ruff check src tests
	$(PYTEST) --no-cov tests/unit
