import pytest
from unittest.mock import Mock, patch
from lb_local.model.credential import Credential
from lb_local.model.service import Service


class TestCredentialViews:
    """Test cases for credential view endpoints."""

    def test_credential_list_requires_authentication(self, client):
        """Test that credential list requires authentication."""
        response = client.get('/credential/list')
        assert response.status_code == 302  # Redirect to login

    def test_credential_list_with_auth(self, authenticated_client):
        """Test authenticated access to credential list."""
        response = authenticated_client.get('/credential/list')
        assert response.status_code == 200

    def test_credential_add_get_requires_authentication(self, client):
        """Test that credential add GET requires authentication."""
        response = client.get('/credential/add')
        assert response.status_code == 302

    def test_credential_add_get_with_auth(self, authenticated_client):
        """Test authenticated access to credential add form."""
        response = authenticated_client.get('/credential/add')
        assert response.status_code == 200
        assert b'add' in response.data.lower() or b'credential' in response.data.lower()

    def test_credential_add_post_requires_authentication(self, client):
        """Test that credential add POST requires authentication."""
        response = client.post('/credential/add', data={
            'service': 'spotify',
            'user_name': 'test_user'
        })
        assert response.status_code == 302

    def test_credential_edit_requires_authentication(self, client):
        """Test that credential edit requires authentication."""
        response = client.get('/credential/1/edit')
        assert response.status_code == 302

    def test_credential_edit_nonexistent_credential(self, authenticated_client):
        """Test editing a non-existent credential returns 404."""
        response = authenticated_client.get('/credential/999/edit')
        assert response.status_code == 404

    def test_credential_delete_requires_authentication(self, client):
        """Test that credential delete requires authentication."""
        response = client.get('/credential/1/delete')
        assert response.status_code == 302

    def test_credential_delete_nonexistent_credential(self, authenticated_client):
        """Test deleting a non-existent credential returns 404."""
        response = authenticated_client.get('/credential/999/delete')
        assert response.status_code == 404

    def test_credential_with_existing_credential(self, authenticated_client, app):
        """Test credential endpoints with an existing credential."""
        # Get or create a test service 
        service, created = Service.get_or_create(
            url='http://test-credential.com',
            defaults={
                'name': 'Test Credential Service',
                'slug': 'test-credential-service',
                'owner_id': 1
            }
        )

        # Create a test credential
        credential = Credential.create(
            service=service,
            user_name='test_user',
            password='test_password',
            shared=False,
            owner_id=1
        )
        
        # Test edit page
        response = authenticated_client.get(f'/credential/{credential.id}/edit')
        assert response.status_code == 200
        
        # Test delete page (should redirect after successful deletion)
        response = authenticated_client.get(f'/credential/{credential.id}/delete')
        assert response.status_code == 302  # Successful deletion redirects
        
        # No need to clean up - already deleted
class TestCredentialAPI:
    """Test cases for credential-related functionality."""

    @patch('lb_local.view.credential.load_credentials')
    def test_load_credentials_mock(self, mock_load_credentials, authenticated_client):
        """Test that credential loading works properly."""
        mock_load_credentials.return_value = ({}, None)

        # Create a service and credential to delete (which will trigger load_credentials)
        service, created = Service.get_or_create(
            url='http://test-load-cred.com',
            defaults={
                'name': 'Load Test Service',
                'slug': 'load-test-service', 
                'owner_id': 1
            }
        )
        credential = Credential.create(
            service=service,
            user_name='load_test_user',
            password='test_password',
            shared=False,
            owner_id=1
        )

        # Delete the credential - this will trigger load_credentials
        response = authenticated_client.get(f'/credential/{credential.id}/delete')
        assert response.status_code == 302
        mock_load_credentials.assert_called()

    def test_credential_add_post_with_auth(self, authenticated_client):
        """Test credential creation with authentication."""
        response = authenticated_client.post('/credential/add', data={
            'service': 'spotify',
            'user_name': 'test_user',
            'client_id': 'test_client',
            'client_secret': 'test_secret',
            'redirect_uri': 'http://localhost:5000/callback'
        })
        # Should redirect on success or show form again if validation fails
        assert response.status_code in [200, 302]
