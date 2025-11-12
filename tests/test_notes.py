import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_create_and_get_note():
    async with AsyncClient(app=app, base_url='http://test') as ac:
        payload = {'title': 'Test Note', 'body': 'This is a test'}
        post_resp = await ac.post('/api/v1/notes', json=payload)
        assert post_resp.status_code == 201
        data = post_resp.json()
        note_id = data['id']
        get_resp = await ac.get(f'/api/v1/notes/{note_id}')
        assert get_resp.status_code == 200
        note = get_resp.json()
        assert note['title'] == payload['title']
        assert note['body'] == payload['body']
