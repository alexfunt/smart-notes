import pytest

pytestmark = pytest.mark.asyncio


async def test_root_returns_ok(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Smart Notes API is running"}


async def test_health_endpoint_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)