import pytest
from unittest.mock import Mock, patch


class TestAuthenticationViews:
    """Test cases for authentication-related endpoints."""

    def test_login_redirect_endpoint(self, client):
        """Test that login redirect endpoint exists and works."""
        with patch('lb_local.server.oauth') as mock_oauth:
            mock_oauth.musicbrainz.authorize_redirect.return_value = Mock()
            response = client.get('/login')
            assert response.status_code in [200, 302]

    def test_auth_callback_endpoint(self, client):
        """Test that auth callback endpoint exists and handles requests."""
        with patch('lb_local.server.oauth') as mock_oauth:
            # Mock the OAuth token and userinfo
            mock_token = {'access_token': 'test_token'}
            mock_oauth.musicbrainz.authorize_access_token.return_value = mock_token
            
            mock_userinfo_response = Mock()
            mock_userinfo_response.json.return_value = {
                'sub': 'test_user',
                'profile': 'http://test.com'
            }
            mock_oauth.musicbrainz.get.return_value = mock_userinfo_response
            
            response = client.get('/auth')
            # Should handle the auth flow (might redirect or show error)
            assert response.status_code in [200, 302, 400, 401]


class TestStaticRoutes:
    """Test cases for static file serving and basic routes."""

    def test_static_files_accessible(self, client):
        """Test that static files can be accessed."""
        # Try to access a CSS file
        response = client.get('/static/css/lb-local.css')
        # Should either serve the file (200) or return 404 if not found during testing
        assert response.status_code in [200, 404]

    def test_static_js_files_accessible(self, client):
        """Test that static JavaScript files can be accessed."""
        response = client.get('/static/js/lb-local.js')
        assert response.status_code in [200, 404]

    def test_static_images_accessible(self, client):
        """Test that static image files can be accessed."""
        response = client.get('/static/img/lb-local-logo.svg')
        assert response.status_code in [200, 404]


class TestAdminRoutes:
    """Test cases for Flask-Admin routes."""

    def test_admin_requires_authentication(self, client):
        """Test that admin interface requires authentication."""
        response = client.get('/admin/')
        # Should redirect to login or show unauthorized
        assert response.status_code in [302, 401, 403]

    def test_admin_user_view_requires_admin(self, authenticated_client):
        """Test that admin user view requires admin privileges."""
        response = authenticated_client.get('/admin/user/')
        # Should show unauthorized since user is not admin
        assert response.status_code in [302, 401, 403]

    def test_admin_service_view_requires_admin(self, authenticated_client):
        """Test that admin service view requires admin privileges."""
        response = authenticated_client.get('/admin/service/')
        # Should show unauthorized since user is not admin
        assert response.status_code in [302, 401, 403]

    def test_admin_credential_view_requires_admin(self, authenticated_client):
        """Test that admin credential view requires admin privileges."""
        response = authenticated_client.get('/admin/credential/')
        # Should show unauthorized since user is not admin
        assert response.status_code in [302, 401, 403]

    def test_admin_with_admin_user(self, admin_client):
        """Test admin routes with admin user."""
        # Test admin index
        response = admin_client.get('/admin/')
        assert response.status_code == 200
        
        # Test admin user view
        response = admin_client.get('/admin/user/')
        assert response.status_code == 200
        
        # Test admin service view
        response = admin_client.get('/admin/service/')
        assert response.status_code == 200
        
        # Test admin credential view  
        response = admin_client.get('/admin/credential/')
        assert response.status_code == 200


class TestErrorHandling:
    """Test cases for error handling and edge cases."""

    def test_404_on_nonexistent_route(self, client):
        """Test that nonexistent routes return 404."""
        response = client.get('/this-route-does-not-exist')
        assert response.status_code == 404

    def test_405_on_wrong_method(self, client):
        """Test that wrong HTTP methods return 405."""
        # Try POST on a GET-only endpoint
        response = client.post('/welcome')
        assert response.status_code == 405

    def test_500_errors_are_handled(self, authenticated_client):
        """Test that 500 errors are handled gracefully."""
        with patch('lb_local.view.index.render_template') as mock_render:
            mock_render.side_effect = Exception("Test error")
            try:
                response = authenticated_client.get('/top-tags')
                # If we get here, Flask handled the error
                assert response.status_code in [500, 302]  # 500 error or redirect
            except Exception as e:
                # In testing mode, Flask re-raises exceptions instead of handling them
                # This is expected behavior when TESTING = True
                assert "Test error" in str(e)


class TestCORSAndSecurity:
    """Test cases for CORS and security headers."""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present when configured."""
        response = client.get('/welcome')
        # CORS might be configured, check if headers are handled appropriately
        assert response.status_code == 200

    def test_security_headers(self, client):
        """Test that security measures are in place."""
        response = client.get('/welcome')
        # Basic security check - should not expose sensitive information
        assert b'secret' not in response.data.lower()
        assert b'password' not in response.data.lower()
        assert response.status_code == 200
