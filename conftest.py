import os
import tempfile
import pytest
from unittest.mock import Mock, patch
from lb_local.server import create_app
from lb_local.database import UserDatabase
from lb_local.model.user import User

try:
    from troi.content_resolver.subsonic import SubsonicDatabase
    from troi.patches.lb_radio_classes.weekly_jams import WeeklyJamsList
except ImportError:
    # Create a mock SubsonicDatabase class when troi is not available
    class SubsonicDatabase:
        def __init__(self, *args, **kwargs):
            pass
        def create(self):
            pass

    # Create a mock WeeklyJamsList class when troi is not available
    class WeeklyJamsList:
        def __init__(self, *args, **kwargs):
            pass
        def get_jams(self):
            return []

@pytest.fixture
def client():
    """Create test client"""
    with patch('lb_local.sync.SyncManager'):
        with patch.dict('os.environ', {
            'DATABASE_FILE': 'test.db',
            'SECRET_KEY': 'test-secret-key',
            'DOMAIN': '127.0.0.1',
            'PORT': '5000',
            'AUTHORIZED_USERS': 'testuser,adminuser',
            'ADMIN_USERS': 'adminuser',
            'SERVICE_USERS': 'testuser,adminuser',
            'MUSICBRAINZ_CLIENT_ID': 'test-client-id',
            'MUSICBRAINZ_CLIENT_SECRET': 'test-client-secret',
        }, clear=True):
            app, oauth = create_app()  # create_app returns a tuple
            app.config['TESTING'] = True
            
            # Register the blueprints (these are normally registered outside create_app)
            from lb_local.view.index import index_bp
            from lb_local.view.service import service_bp
            from lb_local.view.credential import credential_bp
            
            app.register_blueprint(index_bp)
            app.register_blueprint(service_bp, url_prefix="/service")
            app.register_blueprint(credential_bp, url_prefix="/credential")
            
            # Add missing credential index route (bug fix)
            @app.route("/credential/", methods=["GET"])
            def credential_index():
                from flask import redirect, url_for
                return redirect(url_for('credential_bp.credential_list'))
            
            # Add the OAuth routes that are normally registered outside create_app
            @app.route("/login")
            def login_redirect():
                from flask import url_for
                redirect_uri = url_for('auth', _external=True)
                return oauth.musicbrainz.authorize_redirect(redirect_uri)
            
            @app.route('/auth')
            def auth():
                # Mock auth endpoint for testing
                return "Mock auth endpoint", 200
            
            with app.test_client() as client:
                with app.app_context():
                    yield client

@pytest.fixture
def authenticated_client(client):
    """Create a client with authenticated user"""
    # Get or create test user that matches the authorized users
    test_user, created = User.get_or_create(
        name="testuser",
        defaults={
            'login_id': "test-login-id",
            'access_token': "test-access-token"
        }
    )
    
    # Use Flask-Login's test client approach to simulate login
    with client.session_transaction() as sess:
        sess['_user_id'] = test_user.login_id
        sess['_fresh'] = True
        # Set required session data that views expect
        sess['subsonic'] = {
            'url': 'http://test-subsonic.com',
            'username': 'testuser',
            'password': 'testpass'
        }
        sess['cors_url'] = 'http://test-cors.com'
    
    yield client

@pytest.fixture
def admin_client(client):
    """Create a client with admin user"""
    # Get or create admin user
    admin_user, created = User.get_or_create(
        name="adminuser",
        defaults={
            'login_id': "admin-login-id",
            'access_token': "admin-access-token"
        }
    )
    
    # Use Flask-Login's test client approach to simulate admin login
    with client.session_transaction() as sess:
        sess['_user_id'] = admin_user.login_id
        sess['_fresh'] = True
        # Set required session data that views expect
        sess['subsonic'] = {
            'url': 'http://test-subsonic.com',
            'username': 'adminuser',
            'password': 'testpass'
        }
        sess['cors_url'] = 'http://test-cors.com'
    
    yield client

@pytest.fixture
def mock_radio_service():
    """Mock the radio service for testing"""
    with patch('lb_local.view.index.ListenBrainzRadioLocal') as mock_radio:
        # Mock the generate_playlist method
        mock_playlist = Mock()
        mock_playlist.playlists = [Mock()]
        mock_playlist.playlists[0].tracks = []
        mock_radio.return_value.generate_playlist.return_value = mock_playlist
        
        # Mock the radio service instance
        mock_radio_instance = Mock()
        mock_radio_instance.generate_playlist = Mock(return_value=mock_playlist)
        mock_radio_instance.get_prompt_context = Mock(return_value={})
        mock_radio.return_value = mock_radio_instance
        yield mock_radio

@pytest.fixture  
def mock_credentials():
    """Mock credentials loading for testing"""
    with patch('lb_local.view.index.load_credentials') as mock_load:
        mock_load.return_value = ({"SUBSONIC_SERVERS": {}}, "")  # Return tuple with SUBSONIC_SERVERS key
        yield mock_load

@pytest.fixture
def mock_weekly_jams():
    """Mock weekly jams for testing"""
    with patch('lb_local.view.index.WeeklyJams') as mock_jams:
        mock_instance = Mock()
        mock_instance.generate.return_value = Mock()
        mock_jams.return_value = mock_instance
        yield mock_jams

@pytest.fixture
def mock_top_tags():
    """Mock top tags for testing"""
    with patch('lb_local.view.index.TopTags') as mock_tags:
        mock_instance = Mock()
        mock_instance.generate.return_value = Mock()
        mock_tags.return_value = mock_instance
        yield mock_tags

@pytest.fixture
def mock_troi():
    """Mock troi component to avoid import issues during testing"""
    mock = Mock()
    
    # Mock WeeklyJamsList
    mock_weekly = Mock()
    mock_weekly.return_value = Mock()
    mock_weekly.return_value.get_jams.return_value = []
    mock.WeeklyJamsList = mock_weekly
    
    return mock

@pytest.fixture
def app():
    """Create Flask app instance for testing"""
    with patch('lb_local.sync.SyncManager'):
        with patch.dict('os.environ', {
            'DATABASE_FILE': 'test.db',
            'SECRET_KEY': 'test-secret-key',
            'DOMAIN': '127.0.0.1',
            'PORT': '5000',
            'AUTHORIZED_USERS': 'testuser',
            'ADMIN_USERS': 'adminuser',
            'SERVICE_USERS': 'testuser',
            'MUSICBRAINZ_CLIENT_ID': 'test-client-id',
            'MUSICBRAINZ_CLIENT_SECRET': 'test-client-secret',
        }, clear=True):
            app, oauth = create_app()
            app.config['TESTING'] = True
            
            # Register the blueprints
            from lb_local.view.index import index_bp
            from lb_local.view.service import service_bp
            from lb_local.view.credential import credential_bp
            
            app.register_blueprint(index_bp)
            app.register_blueprint(service_bp, url_prefix="/service")
            app.register_blueprint(credential_bp, url_prefix="/credential")
            
            yield app
