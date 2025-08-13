.PHONY: test test-verbose test-coverage test-fast install-test-deps clean help

# Default target
help:
	@echo "Available commands:"
	@echo "  make test              - Run all tests"
	@echo "  make test-verbose      - Run tests with verbose output"
	@echo "  make test-coverage     - Run tests with coverage report"
	@echo "  make test-fast         - Run tests without coverage"
	@echo "  make install-test-deps - Install testing dependencies"
	@echo "  make clean            - Clean up test artifacts"
	@echo "  make help             - Show this help message"

# Install testing dependencies
install-test-deps:
	pip install -r requirements-test.txt

# Run all tests with default settings
test:
	python run_tests.py

# Run tests with verbose output
test-verbose:
	python run_tests.py -v

# Run tests with coverage report
test-coverage:
	python run_tests.py --cov=lb_local --cov-report=term-missing --cov-report=html

# Run tests without coverage for speed
test-fast:
	python run_tests.py --no-cov -q

# Run specific test file
test-index:
	python run_tests.py tests/test_index_views.py

test-service:
	python run_tests.py tests/test_service_views.py

test-credential:
	python run_tests.py tests/test_credential_views.py

test-auth:
	python run_tests.py tests/test_auth_and_misc.py

test-share:
	python run_tests.py tests/test_share_functionality.py

# Run tests matching a pattern
test-pattern:
	@read -p "Enter test pattern: " pattern; \
	python run_tests.py -k "$$pattern"

# Clean up test artifacts
clean:
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "test_*.db*" -delete

# Run linting
lint:
	flake8 lb_local/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 lb_local/ tests/ --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics

# Format code
format:
	black lb_local/ tests/
	isort lb_local/ tests/

# Run a quick smoke test
smoke-test:
	python run_tests.py tests/test_auth_and_misc.py::TestStaticRoutes::test_static_files_accessible -v
