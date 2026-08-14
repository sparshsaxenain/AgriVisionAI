def test_register_and_login(client):
    payload = {"name": "Ravi Test", "phone": "9876500000", "email": "ravi@test.local", "password": "secret1"}
    created = client.post("/auth/register", json=payload)
    assert created.status_code == 201
    assert "password_hash" not in created.json()["user"]
    logged_in = client.post("/auth/login", json={"identifier": "ravi@test.local", "password": "secret1"})
    assert logged_in.status_code == 200
    assert logged_in.json()["access_token"]


def test_wrong_password_is_rejected(client):
    client.post("/auth/register", json={"name": "Farmer", "phone": "1234567890", "password": "secret1"})
    response = client.post("/auth/login", json={"identifier": "1234567890", "password": "wrongpass"})
    assert response.status_code == 401


def test_multiple_phone_only_accounts_are_allowed(client):
    first = client.post("/auth/register", json={"name": "Farmer One", "phone": "1111111111", "password": "secret1"})
    second = client.post("/auth/register", json={"name": "Farmer Two", "phone": "2222222222", "password": "secret2"})
    assert first.status_code == 201
    assert second.status_code == 201
