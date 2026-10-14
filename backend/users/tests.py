import pytest
from rest_framework.test import APIClient
from users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestRegister:
    def test_creates_user_and_returns_token(self, client):
        response = client.post('/api/auth/register', {
            'email': 'test@example.com',
            'password': 'password123',
            'name': 'Test User',
        }, format='json')
        assert response.status_code == 201
        assert 'token' in response.data
        assert response.data['user']['email'] == 'test@example.com'

    def test_rejects_short_password(self, client):
        response = client.post('/api/auth/register', {
            'email': 'test@example.com',
            'password': 'short',
            'name': 'Test User',
        }, format='json')
        assert response.status_code == 400

    def test_rejects_duplicate_email(self, client):
        User.objects.create_user(email='test@example.com', name='Existing', password='password123')
        response = client.post('/api/auth/register', {
            'email': 'test@example.com',
            'password': 'password123',
            'name': 'New User',
        }, format='json')
        assert response.status_code == 400

    def test_rejects_missing_name(self, client):
        response = client.post('/api/auth/register', {
            'email': 'test@example.com',
            'password': 'password123',
        }, format='json')
        assert response.status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_returns_token_on_valid_credentials(self, client):
        User.objects.create_user(email='test@example.com', name='Test', password='password123')
        response = client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'password123',
        }, format='json')
        assert response.status_code == 200
        assert 'token' in response.data
        assert response.data['user']['email'] == 'test@example.com'

    def test_rejects_wrong_password(self, client):
        User.objects.create_user(email='test@example.com', name='Test', password='password123')
        response = client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'wrongpassword',
        }, format='json')
        assert response.status_code == 401

    def test_rejects_missing_email(self, client):
        response = client.post('/api/auth/login', {'password': 'anything'}, format='json')
        assert response.status_code == 400

    def test_rejects_unknown_email(self, client):
        response = client.post('/api/auth/login', {
            'email': 'nobody@example.com',
            'password': 'password123',
        }, format='json')
        assert response.status_code == 401


@pytest.mark.django_db
class TestMe:
    def test_requires_auth(self, client):
        response = client.get('/api/users/me')
        assert response.status_code == 401

    def test_returns_current_user(self, client):
        User.objects.create_user(email='test@example.com', name='Test', password='password123')
        resp = client.post('/api/auth/login', {
            'email': 'test@example.com',
            'password': 'password123',
        }, format='json')
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['token']}")
        response = client.get('/api/users/me')
        assert response.status_code == 200
        assert response.data['user']['email'] == 'test@example.com'
        assert response.data['user']['name'] == 'Test'
