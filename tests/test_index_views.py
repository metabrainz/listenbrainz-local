import pytest
from unittest.mock import Mock, patch


class TestIndexViews:
    """Test cases for index view endpoints."""

    def test_index_redirects_to_welcome_when_not_authenticated(self, client):
        """Test that index redirects unauthenticated users to welcome page."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/welcome' in response.location

    def test_welcome_page_loads(self, client):
        """Test that welcome page loads correctly."""
        response = client.get('/welcome')
        assert response.status_code == 200
        assert b'welcome' in response.data.lower() or b'login' in response.data.lower()

    def test_lb_radio_get_requires_authentication(self, client):
        """Test that LB Radio GET requires authentication."""
        response = client.get('/lb-radio')
        assert response.status_code == 302  # Redirect to login

    def test_lb_radio_get_with_auth(self, authenticated_client, mock_credentials):
        """Test that authenticated users can access LB Radio page."""
        response = authenticated_client.get('/lb-radio')
        assert response.status_code == 200
        assert b'lb-radio' in response.data.lower() or b'radio' in response.data.lower()

    def test_lb_radio_get_with_prompt(self, authenticated_client, mock_credentials):
        """Test LB Radio GET with prompt parameter."""
        response = authenticated_client.get('/lb-radio?prompt=test&title=Test')
        assert response.status_code == 200

    def test_lb_radio_post_requires_authentication(self, client):
        """Test that LB Radio POST requires authentication."""
        response = client.post('/lb-radio', data={'prompt': 'test', 'mode': 'easy'})
        assert response.status_code == 302  # Redirect to login

    def test_lb_radio_post_missing_prompt(self, authenticated_client, mock_credentials):
        """Test LB Radio POST with missing prompt."""
        response = authenticated_client.post('/lb-radio', data={'mode': 'easy'})
        assert response.status_code == 400  # Bad Request

    def test_lb_radio_post_missing_mode(self, authenticated_client, mock_credentials):
        """Test LB Radio POST with missing mode."""
        response = authenticated_client.post('/lb-radio', data={'prompt': 'test'})
        assert response.status_code == 400  # Bad Request

    @patch('lb_local.view.index.SubsonicDatabase')
    def test_lb_radio_post_valid(self, mock_db, authenticated_client, mock_credentials, mock_troi):
        """Test valid LB Radio POST request."""
        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        response = authenticated_client.post('/lb-radio', data={'prompt': 'test', 'mode': 'easy'})
        assert response.status_code == 200

    def test_weekly_jams_get_requires_authentication(self, client):
        """Test that Weekly Jams GET requires authentication."""
        response = client.get('/weekly-jams')
        assert response.status_code == 302

    def test_weekly_jams_get_with_auth(self, authenticated_client, mock_credentials):
        """Test authenticated access to Weekly Jams."""
        response = authenticated_client.get('/weekly-jams')
        assert response.status_code == 200

    def test_weekly_jams_post_requires_authentication(self, client):
        """Test that Weekly Jams POST requires authentication."""
        response = client.post('/weekly-jams', data={'user': 'test'})
        assert response.status_code == 302

    @patch('lb_local.view.index.WeeklyJamsList')
    @patch('lb_local.view.index.SubsonicDatabase')
    def test_weekly_jams_post_valid(self, mock_db, mock_weekly_jams, authenticated_client, mock_credentials):
        """Test valid Weekly Jams POST request."""
        # Mock weekly jams response
        mock_weekly_instance = Mock()
        mock_playlist = Mock()
        mock_playlist.playlists = [Mock()]
        mock_playlist.playlists[0].recordings = []
        mock_playlist.playlists[0].name = "Weekly Jams"
        mock_playlist.playlists[0].description = "Weekly playlist"
        mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
        mock_weekly_instance.generate.return_value = mock_playlist
        mock_weekly_instance.patch.user_feedback.return_value = []
        mock_weekly_jams.return_value = mock_weekly_instance
        
        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        response = authenticated_client.post('/weekly-jams', data={'user': 'test'})
        assert response.status_code == 200

    def test_playlist_create_requires_authentication(self, client):
        """Test that playlist creation requires authentication."""
        response = client.post('/playlist/create', 
                             json={'jspf': '{}', 'service': 'test', 'playlist-name': 'test'})
        assert response.status_code == 302

    def test_top_tags_requires_authentication(self, client):
        """Test that top tags requires authentication."""
        response = client.get('/top-tags')
        assert response.status_code == 302

    @patch('lb_local.view.index.SubsonicDatabase')
    def test_top_tags_with_auth(self, mock_db, authenticated_client, mock_credentials):
        """Test authenticated access to top tags."""
        mock_db_instance = Mock()
        mock_db_instance.fetch_distinct_tags.return_value = []
        mock_db.return_value = mock_db_instance
        
        response = authenticated_client.get('/top-tags')
        assert response.status_code == 200

    def test_tag_page_requires_authentication(self, client):
        """Test that tag page requires authentication."""
        response = client.get('/tag/rock')
        assert response.status_code == 302

    @patch('lb_local.view.index.SubsonicDatabase')
    def test_tag_page_with_auth(self, mock_db, authenticated_client, mock_credentials):
        """Test authenticated access to tag page."""
        mock_db_instance = Mock()
        mock_db_instance.fetch_recordings_by_tag.return_value = []
        mock_db.return_value = mock_db_instance
        
        response = authenticated_client.get('/tag/rock')
        assert response.status_code == 200

    def test_unresolved_requires_authentication(self, client):
        """Test that unresolved page requires authentication."""
        response = client.get('/unresolved')
        assert response.status_code == 302

    @patch('lb_local.view.index.SubsonicDatabase')
    def test_unresolved_with_auth(self, mock_db, authenticated_client, mock_credentials):
        """Test authenticated access to unresolved page."""
        mock_db_instance = Mock()
        mock_db_instance.fetch_unresolved_recordings.return_value = []
        mock_db.return_value = mock_db_instance
        
        response = authenticated_client.get('/unresolved')
        assert response.status_code == 200
