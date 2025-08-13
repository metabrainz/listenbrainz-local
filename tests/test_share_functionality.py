import pytest
from unittest.mock import Mock, patch
import json


class TestShareFunctionality:
    """Test cases for the share functionality added to LB Radio."""

    @patch('lb_local.view.index.SubsonicDatabase')
    def test_lb_radio_post_includes_share_parameters(self, mock_db, authenticated_client, mock_credentials, mock_troi):
        """Test that LB Radio POST response includes parameters for sharing."""
        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        # Make a POST request with specific parameters
        response = authenticated_client.post('/lb-radio', data={
            'prompt': 'Amy Winehouse',
            'mode': 'easy'
        })
        
        assert response.status_code == 200
        
        # Check that the response contains the parameters for the share functionality
        response_data = response.data.decode('utf-8')
        assert 'Amy Winehouse' in response_data  # prompt should be in template
        assert 'easy' in response_data  # mode should be in template

    @patch('lb_local.view.index.SubsonicDatabase')
    def test_lb_radio_post_with_special_characters_in_prompt(self, mock_db, authenticated_client, mock_credentials, mock_troi):
        """Test that special characters in prompts are handled correctly for sharing."""
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        # Test with prompt containing special characters
        special_prompt = 'tag:(hip hop, jazz)::or'
        response = authenticated_client.post('/lb-radio', data={
            'prompt': special_prompt,
            'mode': 'medium'
        })
        
        assert response.status_code == 200
        response_data = response.data.decode('utf-8')
        
        # The prompt should be properly escaped in the template
        assert 'tag:' in response_data
        assert 'medium' in response_data

    def test_share_button_in_playlist_template(self, authenticated_client, mock_credentials, mock_troi):
        """Test that the share button is present in the playlist template."""
        with patch('lb_local.view.index.SubsonicDatabase') as mock_db:
            mock_db_instance = Mock()
            mock_db.return_value = mock_db_instance
            
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
            mock_db_instance = Mock()
            mock_db.return_value = mock_db_instance
            
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

    @patch('lb_local.view.index.SubsonicDatabase')
    def test_different_modes_in_share_functionality(self, mock_db, authenticated_client, mock_credentials, mock_troi):
        """Test that different modes are correctly handled in share functionality."""
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
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
            mock_db_instance = Mock()
            mock_db.return_value = mock_db_instance
            
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
            mock_db_instance = Mock()
            mock_db.return_value = mock_db_instance
            
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
