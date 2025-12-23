.PHONY: help install test lint format clean run dev

# Default target
help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linters (flake8, mypy)"
	@echo "  make format     - Format code (black, isort)"
	@echo "  make clean      - Clean cache files"
	@echo "  make run        - Run chatbot"
	@echo "  make dev        - Setup development environment"

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term

# Run linters
lint:
	flake8 . --exclude=venv,__pycache__,.git --max-line-length=120
	mypy . --exclude venv --ignore-missing-imports

# Format code
format:
	black . --exclude venv
	isort . --skip venv

# Clean cache and temp files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -f .coverage 2>/dev/null || true

# Run chatbot
run:
	python run_chat.py

# Development setup
dev: install
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file from .env.example"; \
		echo "Please edit .env and add your API keys!"; \
	else \
		echo ".env already exists"; \
	fi
	@echo "Development environment ready!"
	@echo "Run 'make test' to verify setup"

# Quick check (format + lint + test)
check: format lint test
	@echo "All checks passed!"
