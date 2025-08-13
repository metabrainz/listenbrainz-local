# Testing Setup for ListenBrainz Local

This document describes the testing infrastructure for ListenBrainz Local.

## Quick Start

1. **Install test dependencies:**
   ```bash
   pip install -r requirements-test.txt
   ```

2. **Run all tests:**
   ```bash
   make test
   # or
   python run_tests.py
   ```

## Test Structure

The test suite is organized into several modules:

### `tests/test_index_views.py`
Tests for the main application views:
- `/` (home/index)
- `/welcome` 
- `/lb-radio` (GET and POST)
- `/weekly-jams` (GET and POST)
- `/playlist/create` (POST)
- `/top-tags`
- `/tag/<tag>`
- `/unresolved`

### `tests/test_service_views.py` 
Tests for service management endpoints:
- `/service/` (list and management)
- `/service/add` (GET and POST)
- `/service/<slug>/edit`
- `/service/<slug>/delete`
- `/service/<slug>/sync/*` (sync functionality)

### `tests/test_credential_views.py`
Tests for credential management:
- `/credential/list`
- `/credential/add` (GET and POST)
- `/credential/<id>/edit`
- `/credential/<id>/delete`

### `tests/test_auth_and_misc.py`
Tests for authentication and miscellaneous functionality:
- Login/logout flows
- OAuth callbacks
- Admin interface access control
- Static file serving
- Error handling
- CORS and security

### `tests/test_share_functionality.py`
Tests for the share functionality:
- Share button presence in templates
- URL parameter passing
- JavaScript function inclusion
- Special character handling in prompts

## Test Fixtures

The test suite uses several pytest fixtures defined in `conftest.py`:

- `app`: Creates a fresh Flask app instance for each test
- `client`: Test client for making HTTP requests
- `authenticated_client`: Pre-authenticated test client
- `admin_client`: Test client with admin privileges
- `mock_troi`: Mocks Troi recommendation engine
- `mock_credentials`: Mocks credential loading

## Running Tests

### Basic Commands

```bash
# Run all tests
make test

# Run with verbose output
make test-verbose

# Run with coverage report
make test-coverage

# Run without coverage (faster)
make test-fast

# Run specific test file
make test-index
make test-service
make test-credential
make test-auth
make test-share

# Run tests matching a pattern
make test-pattern  # Will prompt for pattern

# Clean up test artifacts
make clean
```

### Advanced Usage

```bash
# Run specific test class
python run_tests.py tests/test_index_views.py::TestIndexViews

# Run specific test method
python run_tests.py tests/test_index_views.py::TestIndexViews::test_lb_radio_get_with_auth

# Run tests with specific markers
python run_tests.py -m "not slow"

# Run tests and stop on first failure
python run_tests.py -x

# Run tests with pdb on failure
python run_tests.py --pdb
```

## Test Configuration

### pytest.ini
Contains pytest configuration including:
- Test discovery patterns
- Coverage settings
- Warning filters
- Custom markers

### Environment Variables
Tests use isolated environment variables:
- `DATABASE_FILE`: Temporary test database
- `SECRET_KEY`: Test secret key
- `AUTHORIZED_USERS`: Test user list
- `FLASK_ENV`: Set to 'testing'

## Mocking Strategy

The test suite uses extensive mocking to isolate components:

1. **Database Operations**: SQLite databases are created in temporary files
2. **External Services**: Troi, MusicBrainz OAuth, Subsonic servers
3. **Background Processes**: Sync manager and queues
4. **File System**: Static file serving

## Coverage

The test suite aims for high coverage of:
- ✅ Route accessibility and authentication
- ✅ Basic request/response cycles  
- ✅ Error handling (4xx, 5xx)
- ✅ Template rendering
- ✅ Admin interface security
- ✅ Share functionality

Coverage reports are generated in HTML format in `htmlcov/` directory.

## Continuous Integration

Tests are designed to run in CI environments:
- No external dependencies
- Fast execution (< 30 seconds typical)
- Deterministic results
- Proper cleanup of temporary files

## Adding New Tests

When adding new endpoints or functionality:

1. Add route tests to appropriate test file
2. Test both authenticated and unauthenticated access
3. Test error conditions
4. Mock external dependencies
5. Verify template rendering if applicable
6. Add integration tests if the feature spans multiple components

Example new test:
```python
def test_new_endpoint_requires_auth(self, client):
    """Test that new endpoint requires authentication."""
    response = client.get('/new-endpoint')
    assert response.status_code == 302  # Redirect to login

def test_new_endpoint_with_auth(self, authenticated_client):
    """Test authenticated access to new endpoint."""
    response = authenticated_client.get('/new-endpoint')
    assert response.status_code == 200
    assert b'expected-content' in response.data
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `lb_local` package is in Python path
2. **Database Errors**: Temporary databases should auto-clean, but check for leftover `.db` files
3. **Port Conflicts**: Tests use mock servers, but check for conflicting processes
4. **Permission Errors**: Ensure write access to temp directory

### Debug Mode

Run tests with verbose output and debugging:
```bash
python run_tests.py -v -s --tb=long --pdb
```

This will:
- Show verbose test names
- Not capture stdout/stderr  
- Show full tracebacks
- Drop into debugger on failures
