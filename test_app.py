import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home(client):
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'running'
    print("✅ Home route test passed!")

def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    print("✅ Health check test passed!")

def test_add(client):
    response = client.get('/add/3/4')
    assert response.status_code == 200
    data = response.get_json()
    assert data['result'] == 7
    print("✅ Add route test passed!")

def test_version(client):
    response = client.get('/version')
    assert response.status_code == 200
    data = response.get_json()
    assert 'version' in data
    assert 'environment' in data
    print("✅ Version route test passed!")
