import pytest
from unittest.mock import Mock, patch
from lb_local.model.service import Service


class TestServiceViews:
    """Test cases for service view endpoints."""

    def test_service_index_requires_authentication(self, client):
        """Test that service index requires authentication."""
        response = client.get('/service/')
        assert response.status_code == 302  # Redirect to login

    def test_service_index_with_auth(self, authenticated_client):
        """Test authenticated access to service index."""
        response = authenticated_client.get('/service/')
        assert response.status_code == 200

    def test_service_list_requires_authentication(self, client):
        """Test that service list requires authentication."""
        response = client.get('/service/list')
        assert response.status_code == 302

    def test_service_list_with_auth(self, authenticated_client):
        """Test authenticated access to service list."""
        response = authenticated_client.get('/service/list')
        assert response.status_code == 200

    def test_service_add_get_requires_authentication(self, client):
        """Test that service add GET requires authentication."""
        response = client.get('/service/add')
        assert response.status_code == 302

    def test_service_add_get_with_auth(self, authenticated_client):
        """Test authenticated access to service add form."""
        response = authenticated_client.get('/service/add')
        assert response.status_code == 200
        assert b'add' in response.data.lower() or b'service' in response.data.lower()

    def test_service_add_post_requires_authentication(self, client):
        """Test that service add POST requires authentication."""
        response = client.post('/service/add', data={
            'name': 'Test Service',
            'url': 'http://test.com',
            'username': 'test',
            'password': 'test'
        })
        assert response.status_code == 302

    @patch('lb_local.view.service.SubsonicDatabase')
    def test_service_add_post_valid(self, mock_db, authenticated_client):
        """Test valid service creation."""
        mock_db_instance = Mock()
        mock_db_instance.test_connection.return_value = True
        mock_db.return_value = mock_db_instance
        
        response = authenticated_client.post('/service/add', data={
            'name': 'Test Service',
            'url': 'http://test.com',
            'username': 'test',
            'password': 'test'
        })
        # Should redirect on success
        assert response.status_code in [200, 302]

    def test_service_edit_requires_authentication(self, client):
        """Test that service edit requires authentication."""
        response = client.get('/service/test-service/edit')
        assert response.status_code == 302

    def test_service_edit_nonexistent_service(self, authenticated_client):
        """Test editing a non-existent service returns 404."""
        response = authenticated_client.get('/service/nonexistent/edit')
        assert response.status_code == 404

    def test_service_delete_requires_authentication(self, client):
        """Test that service delete requires authentication."""
        response = client.get('/service/test-service/delete')
        assert response.status_code == 302

    def test_service_delete_nonexistent_service(self, authenticated_client):
        """Test deleting a non-existent service returns 404."""
        response = authenticated_client.get('/service/nonexistent/delete')
        assert response.status_code == 404

    def test_service_sync_requires_authentication(self, client):
        """Test that service sync page requires authentication."""
        response = client.get('/service/test-service/sync')
        assert response.status_code == 302

    def test_service_sync_nonexistent_service(self, authenticated_client):
        """Test sync page for non-existent service returns 404."""
        response = authenticated_client.get('/service/nonexistent/sync')
        assert response.status_code == 404

    def test_service_sync_start_requires_authentication(self, client):
        """Test that sync start requires authentication."""
        response = client.post('/service/test-service/sync/start')
        assert response.status_code == 302

    def test_service_sync_start_metadata_only_requires_authentication(self, client):
        """Test that metadata-only sync start requires authentication."""
        response = client.post('/service/test-service/sync/start/metadata-only')
        assert response.status_code == 302

    def test_service_sync_log_requires_authentication(self, client):
        """Test that sync log requires authentication."""
        response = client.get('/service/test-service/sync/log')
        assert response.status_code == 302

    def test_service_sync_full_log_requires_authentication(self, client):
        """Test that sync full log requires authentication."""
        response = client.get('/service/test-service/sync/full-log')
        assert response.status_code == 302

    @patch('lb_local.view.service.SubsonicDatabase')
    def test_service_with_existing_service(self, mock_db, authenticated_client, app):
        """Test service endpoints with an existing service."""
        with app.app_context():
            # Create a test service
            service = Service.create(
                name='Test Service',
                slug='test-service',
                url='http://test.com',
                username='test',
                password='test',
                owner_id=1
            )
            
            # Test edit page
            response = authenticated_client.get(f'/service/{service.slug}/edit')
            assert response.status_code == 200
            
            # Test delete page
            response = authenticated_client.get(f'/service/{service.slug}/delete')
            assert response.status_code == 200
            
            # Test sync page
            response = authenticated_client.get(f'/service/{service.slug}/sync')
            assert response.status_code == 200
            
            # Clean up
            service.delete_instance()


class TestServiceAPI:
    """Test cases for service-related API endpoints."""

    def test_sync_endpoints_exist(self, authenticated_client, app):
        """Test that sync-related endpoints exist and handle requests properly."""
        with app.app_context():
            # Create a test service
            service = Service.create(
                name='Test Service',
                slug='test-service',
                url='http://test.com',
                username='test',
                password='test',
                owner_id=1
            )
            
            # Test sync log endpoint
            response = authenticated_client.get(f'/service/{service.slug}/sync/log')
            assert response.status_code == 200
            
            # Test full sync log endpoint
            response = authenticated_client.get(f'/service/{service.slug}/sync/full-log')
            assert response.status_code == 200
            
            # Clean up
            service.delete_instance()
