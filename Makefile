.PHONY: help install install-dev test lint check tidy version-dev version-release clean docs docs-serve
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

install-dev: ## Install development dependencies
	uv sync --extra dev

test: install-dev ## Run tests (auto-installs dev dependencies)
	uv run pytest

test-cov: install-dev ## Run tests with coverage (auto-installs dev dependencies)
	uv run pytest --cov=nllm --cov-report=html --cov-report=term

lint: install-dev ## Run linters (auto-installs dev dependencies)
	uv run ruff check nllm tests
	uv run pyright nllm

lint-all: install-dev ## Run linters including tests (auto-installs dev dependencies)
	uv run ruff check nllm tests
	uv run pyright nllm tests

tidy: install-dev ## Fix formatting and linting issues (auto-installs dev dependencies)
	uv run ruff format nllm tests
	uv run ruff check --fix nllm tests
	uv run black nllm tests

check: lint ## Run all checks (alias for lint)

version-dev: ## Bump development version
	@current_version=$$(grep -E "^__version__ = " nllm/__init__.py | cut -d '"' -f2); \
	if [[ $$current_version =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$$ ]]; then \
		major=$${BASH_REMATCH[1]}; \
		minor=$${BASH_REMATCH[2]}; \
		patch=$${BASH_REMATCH[3]}; \
		new_patch=$$((patch + 1)); \
		new_version="$$major.$$minor.$$new_patch"; \
		sed -i '' 's/__version__ = ".*"/__version__ = "'$$new_version'"/' nllm/__init__.py; \
		echo "Version bumped to $$new_version"; \
	else \
		echo "Could not parse current version: $$current_version"; \
		exit 1; \
	fi

version-release: ## Bump minor version for release
	@current_version=$$(grep -E "^__version__ = " nllm/__init__.py | cut -d '"' -f2); \
	if [[ $$current_version =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$$ ]]; then \
		major=$${BASH_REMATCH[1]}; \
		minor=$${BASH_REMATCH[2]}; \
		new_minor=$$((minor + 1)); \
		new_version="$$major.$$new_minor.0"; \
		sed -i '' 's/__version__ = ".*"/__version__ = "'$$new_version'"/' nllm/__init__.py; \
		echo "Version bumped to $$new_version"; \
	else \
		echo "Could not parse current version: $$current_version"; \
		exit 1; \
	fi

build: ## Build package for distribution
	uv build

install-package: build ## Install package globally with pipx
	pipx install . -f

uninstall-package: ## Uninstall package from pipx
	pipx uninstall nllm

clean: ## Clean up build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf docs/sphinx/_build/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docs: install-dev ## Build Sphinx documentation (auto-installs dev dependencies)
	cd docs/sphinx && uv run python -m sphinx -b html . _build/html
	@echo "Documentation built! Open docs/sphinx/_build/html/index.html in your browser"

docs-serve: docs ## Build and serve documentation locally (auto-installs dev dependencies)
	cd docs/sphinx/_build/html && python -m http.server 8080 &
	@echo "Documentation server running at http://localhost:8080"
	@echo "Press Ctrl+C to stop the server"

docker-build: ## Build Docker image
	docker build -t nllm:latest .

docker-run: ## Run Docker container
	docker run --rm -it nllm:latest

