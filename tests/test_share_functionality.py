import pytest
from unittest.mock import Mock, patch
import json


class TestShareFunctionality:
    """Test cases for the share functionality added to LB Radio."""

    @patch('lb_local.view.index.ListenBrainzRadioLocal')
    @patch('lb_local.view.index.SubsonicDatabase')
    def test_lb_radio_post_includes_share_parameters(self, mock_db, mock_radio, authenticated_client, mock_credentials):
        """Test that LB Radio POST response includes parameters for sharing."""
        # Mock database
        mock_db_instance = Mock()
        mock_db_instance.metadata_sanity_check.return_value = []
        mock_db.return_value = mock_db_instance
        
        # Mock radio
        mock_radio_instance = Mock()
        mock_playlist = Mock()
        mock_playlist.playlists = [Mock()]
        # Create mock recording with proper structure
        mock_recording = Mock()
        mock_recording.mbid = "test-recording-mbid"
        mock_recording.name = "Test Song"
        mock_recording.listenbrainz = {"file_source": "test-service"}
        mock_recording.musicbrainz = {"subsonic_id": "123", "file_source": "test-service"}
        # Mock release
        mock_recording.release = Mock()
        mock_recording.release.mbid = "test-release-mbid"
        mock_recording.release.name = "Test Album"
        # Mock artist credit with artists list
        mock_recording.artist_credit = Mock()
        mock_artist = Mock()
        mock_artist.mbid = "test-artist-mbid"
        mock_artist.name = "Test Artist"
        mock_recording.artist_credit.artists = [mock_artist]
        mock_playlist.playlists[0].recordings = [mock_recording]
        mock_playlist.playlists[0].name = "LB Radio"
        mock_playlist.playlists[0].description = "Generated playlist"
        mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
        mock_radio_instance.generate.return_value = mock_playlist
        mock_radio_instance.patch.user_feedback.return_value = []  # Return empty list for hints
        mock_radio.return_value = mock_radio_instance
        
        # Make a POST request with specific parameters
        response = authenticated_client.post('/lb-radio', data={
            'prompt': 'Amy Winehouse',
            'mode': 'easy'
        })
        
        assert response.status_code == 200
        
        # Check that the response contains the parameters for the share functionality
        response_data = response.data.decode('utf-8')
        assert 'Amy%20Winehouse' in response_data  # prompt should be URL-encoded in template
        assert 'easy' in response_data  # mode should be in template

    @patch('lb_local.view.index.ListenBrainzRadioLocal')
    @patch('lb_local.view.index.SubsonicDatabase')
    def test_lb_radio_post_with_special_characters_in_prompt(self, mock_db, mock_radio, authenticated_client, mock_credentials):
        """Test that special characters in prompts are handled correctly for sharing."""
        # Mock database
        mock_db_instance = Mock()
        mock_db_instance.metadata_sanity_check.return_value = []
        mock_db.return_value = mock_db_instance
        
        # Mock radio
        mock_radio_instance = Mock()
        mock_playlist = Mock()
        mock_playlist.playlists = [Mock()]
        # Create mock recording with proper structure
        mock_recording = Mock()
        mock_recording.mbid = "test-recording-mbid-2"
        mock_recording.name = "Test Song 2"
        mock_recording.listenbrainz = {"file_source": "test-service"}
        mock_recording.musicbrainz = {"subsonic_id": "456", "file_source": "test-service"}
        # Mock release
        mock_recording.release = Mock()
        mock_recording.release.mbid = "test-release-mbid-2"
        mock_recording.release.name = "Test Album 2"
        # Mock artist credit with artists list
        mock_recording.artist_credit = Mock()
        mock_artist = Mock()
        mock_artist.mbid = "test-artist-mbid-2"
        mock_artist.name = "Test Artist 2"
        mock_recording.artist_credit.artists = [mock_artist]
        mock_playlist.playlists[0].recordings = [mock_recording]
        mock_playlist.playlists[0].name = "LB Radio"
        mock_playlist.playlists[0].description = "Generated playlist"
        mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
        mock_radio_instance.generate.return_value = mock_playlist
        mock_radio_instance.patch.user_feedback.return_value = []  # Return empty list for hints
        mock_radio.return_value = mock_radio_instance
        
        # Test with prompt containing special characters
        special_prompt = 'tag:(hip hop, jazz)::or'
        response = authenticated_client.post('/lb-radio', data={
            'prompt': special_prompt,
            'mode': 'medium'
        })
        
        assert response.status_code == 200
        response_data = response.data.decode('utf-8')
        
        # The prompt should be properly escaped in the template
        # 'tag:(hip hop, jazz)::or' -> 'tag%3A%28hip%20hop%2C%20jazz%29%3A%3Aor'
        assert 'tag%3A' in response_data  # 'tag:' URL-encoded
        assert 'medium' in response_data

    def test_share_button_in_playlist_template(self, authenticated_client, mock_credentials, mock_troi):
        """Test that the share button is present in the playlist template."""
        with patch('lb_local.view.index.SubsonicDatabase') as mock_db:
            with patch('lb_local.view.index.ListenBrainzRadioLocal') as mock_radio:
                mock_db_instance = Mock()
                mock_db_instance.metadata_sanity_check.return_value = []
                mock_db.return_value = mock_db_instance
                
                # Mock radio with complete structure
                mock_radio_instance = Mock()
                mock_playlist = Mock()
                mock_playlist.playlists = [Mock()]
                # Create mock recording with proper structure
                mock_recording = Mock()
                mock_recording.mbid = "test-recording-mbid"
                mock_recording.name = "Test Song"
                mock_recording.listenbrainz = {"file_source": "test-service"}
                mock_recording.musicbrainz = {"subsonic_id": "123", "file_source": "test-service"}
                # Mock release
                mock_recording.release = Mock()
                mock_recording.release.mbid = "test-release-mbid"
                mock_recording.release.name = "Test Album"
                # Mock artist credit with artists list
                mock_recording.artist_credit = Mock()
                mock_artist = Mock()
                mock_artist.mbid = "test-artist-mbid"
                mock_artist.name = "Test Artist"
                mock_recording.artist_credit.artists = [mock_artist]
                mock_playlist.playlists[0].recordings = [mock_recording]
                mock_playlist.playlists[0].name = "LB Radio"
                mock_playlist.playlists[0].description = "Generated playlist"
                mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
                mock_radio_instance.generate.return_value = mock_playlist
                mock_radio_instance.patch.user_feedback.return_value = []
                mock_radio.return_value = mock_radio_instance
                
                response = authenticated_client.post('/lb-radio', data={
                    'prompt': 'test prompt',
                    'mode': 'easy'
                })
                
                assert response.status_code == 200
                response_data = response.data.decode('utf-8')
                
                # Check for share button elements
                assert 'fa-share-nodes' in response_data
                assert 'sharePlaylist()' in response_data
                assert 'Share this playlist' in response_data

    def test_share_javascript_function_present(self, authenticated_client, mock_credentials, mock_troi):
        """Test that the share JavaScript function is included in the response."""
        with patch('lb_local.view.index.SubsonicDatabase') as mock_db:
            with patch('lb_local.view.index.ListenBrainzRadioLocal') as mock_radio:
                mock_db_instance = Mock()
                mock_db_instance.metadata_sanity_check.return_value = []
                mock_db.return_value = mock_db_instance
                
                # Mock radio with complete structure
                mock_radio_instance = Mock()
                mock_playlist = Mock()
                mock_playlist.playlists = [Mock()]
                # Create mock recording with proper structure
                mock_recording = Mock()
                mock_recording.mbid = "test-recording-mbid"
                mock_recording.name = "Test Song"
                mock_recording.listenbrainz = {"file_source": "test-service"}
                mock_recording.musicbrainz = {"subsonic_id": "123", "file_source": "test-service"}
                # Mock release
                mock_recording.release = Mock()
                mock_recording.release.mbid = "test-release-mbid"
                mock_recording.release.name = "Test Album"
                # Mock artist credit with artists list
                mock_recording.artist_credit = Mock()
                mock_artist = Mock()
                mock_artist.mbid = "test-artist-mbid"
                mock_artist.name = "Test Artist"
                mock_recording.artist_credit.artists = [mock_artist]
                mock_playlist.playlists[0].recordings = [mock_recording]
                mock_playlist.playlists[0].name = "LB Radio"
                mock_playlist.playlists[0].description = "Generated playlist"
                mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
                mock_radio_instance.generate.return_value = mock_playlist
                mock_radio_instance.patch.user_feedback.return_value = []
                mock_radio.return_value = mock_radio_instance
                
                response = authenticated_client.post('/lb-radio', data={
                    'prompt': 'test',
                    'mode': 'hard'
                })
                
                assert response.status_code == 200
                response_data = response.data.decode('utf-8')
                
                # Check for JavaScript function components
                assert 'function sharePlaylist()' in response_data
            assert 'navigator.clipboard' in response_data
            assert 'Share link copied to clipboard!' in response_data

    @patch('lb_local.view.index.ListenBrainzRadioLocal')
    @patch('lb_local.view.index.SubsonicDatabase')
    def test_different_modes_in_share_functionality(self, mock_db, mock_radio, authenticated_client, mock_credentials, mock_troi):
        """Test that different modes are correctly handled in share functionality."""
        mock_db_instance = Mock()
        mock_db_instance.metadata_sanity_check.return_value = []
        mock_db.return_value = mock_db_instance
        
        # Mock radio with complete structure
        mock_radio_instance = Mock()
        mock_playlist = Mock()
        mock_playlist.playlists = [Mock()]
        # Create mock recording with proper structure
        mock_recording = Mock()
        mock_recording.mbid = "test-recording-mbid"
        mock_recording.name = "Test Song"
        mock_recording.listenbrainz = {"file_source": "test-service"}
        mock_recording.musicbrainz = {"subsonic_id": "123", "file_source": "test-service"}
        # Mock release
        mock_recording.release = Mock()
        mock_recording.release.mbid = "test-release-mbid"
        mock_recording.release.name = "Test Album"
        # Mock artist credit with artists list
        mock_recording.artist_credit = Mock()
        mock_artist = Mock()
        mock_artist.mbid = "test-artist-mbid"
        mock_artist.name = "Test Artist"
        mock_recording.artist_credit.artists = [mock_artist]
        mock_playlist.playlists[0].recordings = [mock_recording]
        mock_playlist.playlists[0].name = "LB Radio"
        mock_playlist.playlists[0].description = "Generated playlist"
        mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
        mock_radio_instance.generate.return_value = mock_playlist
        mock_radio_instance.patch.user_feedback.return_value = []
        mock_radio.return_value = mock_radio_instance
        
        modes = ['easy', 'medium', 'hard']
        
        for mode in modes:
            response = authenticated_client.post('/lb-radio', data={
                'prompt': 'test artist',
                'mode': mode
            })
            
            assert response.status_code == 200
            response_data = response.data.decode('utf-8')
            assert mode in response_data

    def test_share_url_construction_in_template(self, authenticated_client, mock_credentials, mock_troi):
        """Test that the share URL construction logic is present in the template."""
        with patch('lb_local.view.index.SubsonicDatabase') as mock_db:
            with patch('lb_local.view.index.ListenBrainzRadioLocal') as mock_radio:
                mock_db_instance = Mock()
                mock_db_instance.metadata_sanity_check.return_value = []
                mock_db.return_value = mock_db_instance
                
                # Mock radio with complete structure
                mock_radio_instance = Mock()
                mock_playlist = Mock()
                mock_playlist.playlists = [Mock()]
                # Create mock recording with proper structure
                mock_recording = Mock()
                mock_recording.mbid = "test-recording-mbid"
                mock_recording.name = "Test Song"
                mock_recording.listenbrainz = {"file_source": "test-service"}
                mock_recording.musicbrainz = {"subsonic_id": "123", "file_source": "test-service"}
                # Mock release
                mock_recording.release = Mock()
                mock_recording.release.mbid = "test-release-mbid"
                mock_recording.release.name = "Test Album"
                # Mock artist credit with artists list
                mock_recording.artist_credit = Mock()
                mock_artist = Mock()
                mock_artist.mbid = "test-artist-mbid"
                mock_artist.name = "Test Artist"
                mock_recording.artist_credit.artists = [mock_artist]
                mock_playlist.playlists[0].recordings = [mock_recording]
                mock_playlist.playlists[0].name = "LB Radio"
                mock_playlist.playlists[0].description = "Generated playlist"
                mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
                mock_radio_instance.generate.return_value = mock_playlist
                mock_radio_instance.patch.user_feedback.return_value = []
                mock_radio.return_value = mock_radio_instance
                
                response = authenticated_client.post('/lb-radio', data={
                    'prompt': 'artist:(test)',
                    'mode': 'easy'
                })
                
                assert response.status_code == 200
                response_data = response.data.decode('utf-8')
            
            # Check for URL construction elements
            assert '/lb-radio' in response_data
            assert 'window.location.origin' in response_data
            assert 'prompt=' in response_data
            assert 'mode=' in response_data

    def test_share_error_handling_in_template(self, authenticated_client, mock_credentials, mock_troi):
        """Test that share functionality includes error handling."""
        with patch('lb_local.view.index.SubsonicDatabase') as mock_db:
            with patch('lb_local.view.index.ListenBrainzRadioLocal') as mock_radio:
                mock_db_instance = Mock()
                mock_db_instance.metadata_sanity_check.return_value = []
                mock_db.return_value = mock_db_instance
                
                # Mock radio with complete structure
                mock_radio_instance = Mock()
                mock_playlist = Mock()
                mock_playlist.playlists = [Mock()]
                # Create mock recording with proper structure
                mock_recording = Mock()
                mock_recording.mbid = "test-recording-mbid"
                mock_recording.name = "Test Song"
                mock_recording.listenbrainz = {"file_source": "test-service"}
                mock_recording.musicbrainz = {"subsonic_id": "123", "file_source": "test-service"}
                # Mock release
                mock_recording.release = Mock()
                mock_recording.release.mbid = "test-release-mbid"
                mock_recording.release.name = "Test Album"
                # Mock artist credit with artists list
                mock_recording.artist_credit = Mock()
                mock_artist = Mock()
                mock_artist.mbid = "test-artist-mbid"
                mock_artist.name = "Test Artist"
                mock_recording.artist_credit.artists = [mock_artist]
                mock_playlist.playlists[0].recordings = [mock_recording]
                mock_playlist.playlists[0].name = "LB Radio"
                mock_playlist.playlists[0].description = "Generated playlist"
                mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
                mock_radio_instance.generate.return_value = mock_playlist
                mock_radio_instance.patch.user_feedback.return_value = []
                mock_radio.return_value = mock_radio_instance
                
                response = authenticated_client.post('/lb-radio', data={
                    'prompt': 'test',
                    'mode': 'easy'
                })
                
                assert response.status_code == 200
                response_data = response.data.decode('utf-8')
                
                # Check for error handling in JavaScript
                assert '.catch(' in response_data
                assert 'showShareUrl' in response_data  # fallback function

    @patch('lb_local.view.index.SubsonicDatabase')
    def test_share_with_empty_prompt_handling(self, mock_db, authenticated_client, mock_credentials):
        """Test that share functionality handles edge cases properly."""
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        # Mock troi to return empty playlist
        with patch('lb_local.view.index.ListenBrainzRadioLocal') as mock_radio:
            mock_playlist = Mock()
            mock_playlist.playlists = [Mock()]
            mock_playlist.playlists[0].recordings = []
            mock_playlist.playlists[0].name = "Empty Playlist"
            mock_playlist.playlists[0].description = "No results"
            mock_playlist.get_jspf.return_value = {"playlist": {"track": []}}
            
            mock_radio_instance = Mock()
            mock_radio_instance.generate.return_value = mock_playlist
            mock_radio_instance.patch.user_feedback.return_value = ["No recordings found"]
            mock_radio.return_value = mock_radio_instance
            
            response = authenticated_client.post('/lb-radio', data={
                'prompt': '',  # Empty prompt
                'mode': 'easy'
            })
            
            assert response.status_code == 200
            # Should still include share functionality even with empty results
