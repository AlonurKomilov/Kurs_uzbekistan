# Testing Guide

## Overview
This project uses `pytest` for testing with async support via `pytest-asyncio`.

## Setup Test Environment

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create Test Database
```bash
# Create test database
createdb kubot_test

# Or using psql
psql -U postgres -c "CREATE DATABASE kubot_test;"
```

### 3. Set Environment Variables
```bash
export DATABASE_URL="postgresql+asyncpg://kubot:kubot_password@localhost:5432/kubot_test"
export BOT_TOKEN="test_token_123456"
export SQL_DEBUG="false"
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=. --cov-report=html --cov-report=term
```

### Run Specific Test File
```bash
pytest tests/test_repos.py
```

### Run Specific Test Class
```bash
pytest tests/test_repos.py::TestUserRepository
```

### Run Specific Test Method
```bash
pytest tests/test_repos.py::TestUserRepository::test_create_user
```

### Run with Verbose Output
```bash
pytest -v
```

### Run with Print Statements
```bash
pytest -s
```

## Test Structure

```
tests/
├── conftest.py           # Pytest configuration and fixtures
├── test_repos.py         # Repository tests
├── test_validation.py    # Validation utility tests
└── test_*.py            # Additional test files
```

## Writing Tests

### Example Test
```python
import pytest
from core.repos import UserRepository

@pytest.mark.asyncio
async def test_create_user(db_session, sample_user_data):
    """Test creating a new user."""
    repo = UserRepository(db_session)
    
    user = await repo.create_user(
        sample_user_data["tg_user_id"],
        sample_user_data["lang"]
    )
    
    assert user.tg_user_id == sample_user_data["tg_user_id"]
```

## Fixtures

### Available Fixtures
- `db_session`: Database session for tests
- `sample_user_data`: Sample user data dictionary
- `sample_bank_data`: Sample bank data dictionary
- `sample_rate_data`: Sample rate data dictionary

## Coverage Goals

- **Minimum**: 50% overall coverage
- **Target**: 70% overall coverage
- **Critical Modules**: 80%+ coverage
  - `core/repos.py`
  - `core/validation.py`
  - `api/utils/telegram_auth.py`

## Continuous Integration

### GitHub Actions (recommended)
Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: kubot
          POSTGRES_PASSWORD: kubot_password
          POSTGRES_DB: kubot_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://kubot:kubot_password@localhost:5432/kubot_test
          BOT_TOKEN: test_token_123456
        run: |
          pytest --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Cleanup**: Use fixtures to ensure proper cleanup
3. **Mocking**: Mock external services (Telegram API, etc.)
4. **Naming**: Use descriptive test names
5. **Assertions**: Test one thing per test method
6. **Speed**: Keep tests fast; use test database

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
pg_isready

# Check database exists
psql -U kubot -d kubot_test -c "SELECT 1;"
```

### Import Errors
```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Async Issues
Make sure to:
- Use `@pytest.mark.asyncio` decorator
- Use `async def` for test functions
- `await` async calls
