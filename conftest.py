import os
import tempfile
import pytest
from unittest.mock import Mock, patch
from lb_local.server import create_app
from lb_local.database import UserDatabase
from lb_local.model.user import User
from troi.content_resolver.subsonic import SubsonicDatabase


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Create a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp()
    
    # Mock environment variables
    with patch.dict(os.environ, {
        'DATABASE_FILE': db_path,
        'SECRET_KEY': 'test-secret-key',
        'DOMAIN': 'http://localhost',
        'PORT': '5000',
        'AUTHORIZED_USERS': 'test_user',
        'ADMIN_USERS': 'test_admin',
        'SERVICE_USERS': 'test_service',
        'MUSICBRAINZ_CLIENT_ID': 'test_client_id',
        'MUSICBRAINZ_CLIENT_SECRET': 'test_client_secret'
    }):
        # Mock the sync manager to prevent background processes during tests
        with patch('lb_local.server.SyncManager'):
            app, oauth = create_app()
            app.config['TESTING'] = True
            app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
            
            # Create the database tables
            udb = UserDatabase(db_path, False)
            udb.create()
            
            # Create subsonic database tables
            class Config:
                def __init__(self, **entries):
                    self.__dict__.update(entries)
            
            db = SubsonicDatabase(db_path, Config(**{}), quiet=True)
            db.create()
            
            yield app
    
    # Clean up
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def authenticated_client(app, client):
    """A test client with an authenticated user."""
    with app.app_context():
        # Create a test user
        test_user = User.create(
            login_id='test_user',
            access_token='test_token',
            refresh_token='test_refresh',
            access_token_expires_at=None,
            user_id=1,
            is_admin=False
        )
        
        # Mock the login session
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.user_id)
            sess['_fresh'] = True
            sess['subsonic'] = {
                'servers': {},
                'current_server': None
            }
    
    return client


@pytest.fixture
def admin_client(app, client):
    """A test client with an authenticated admin user."""
    with app.app_context():
        # Create an admin user
        admin_user = User.create(
            login_id='test_admin',
            access_token='admin_token',
            refresh_token='admin_refresh',
            access_token_expires_at=None,
            user_id=2,
            is_admin=True
        )
        
        # Mock the login session
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.user_id)
            sess['_fresh'] = True
            sess['subsonic'] = {
                'servers': {},
                'current_server': None
            }
    
    return client


@pytest.fixture
def mock_troi():
    """Mock the troi components to prevent external dependencies."""
    with patch('lb_local.view.index.ListenBrainzRadioLocal') as mock_radio:
        # Mock the radio response
        mock_playlist = Mock()
        mock_playlist.playlists = [Mock()]
        mock_playlist.playlists[0].recordings = []
        mock_playlist.playlists[0].name = "Test Playlist"
        mock_playlist.playlists[0].description = "Test Description"
        mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
        
        mock_radio_instance = Mock()
        mock_radio_instance.generate.return_value = mock_playlist
        mock_radio_instance.patch.user_feedback.return_value = []
        mock_radio.return_value = mock_radio_instance
        
        yield mock_radio_instance


@pytest.fixture
def mock_credentials():
    """Mock credential loading to prevent database dependencies."""
    with patch('lb_local.view.index.load_credentials') as mock_load:
        mock_load.return_value = (
            {
                'SUBSONIC_SERVERS': {
                    'test_server': {
                        'owner_id': 1,
                        'url': 'http://test.com',
                        'username': 'test',
                        'password': 'test'
                    }
                }
            },
            None
        )
        yield mock_load
