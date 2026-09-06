from __future__ import annotations

import json
import time

import pytest

from app.core.errors import UnauthorizedError
from app.integrations.telegram import build_init_data, verify_init_data

BOT_TOKEN = "123456:TEST-BOT-TOKEN"
USER = {"id": 555, "first_name": "Anna", "username": "anna", "language_code": "ru"}


def test_valid_init_data_is_accepted():
    init_data = build_init_data(BOT_TOKEN, USER)
    parsed = verify_init_data(init_data, BOT_TOKEN)
    assert parsed.user.id == 555
    assert parsed.user.username == "anna"


def test_tampered_payload_is_rejected():
    init_data = build_init_data(BOT_TOKEN, USER)
    forged_user = json.dumps({**USER, "id": 999}, separators=(",", ":"))
    tampered = init_data.replace(
        init_data.split("user=")[1].split("&")[0],
        forged_user.replace(" ", "%20"),
    )
    with pytest.raises(UnauthorizedError):
        verify_init_data(tampered, BOT_TOKEN)


def test_wrong_bot_token_is_rejected():
    init_data = build_init_data(BOT_TOKEN, USER)
    with pytest.raises(UnauthorizedError):
        verify_init_data(init_data, "999999:OTHER-TOKEN")


def test_missing_hash_is_rejected():
    with pytest.raises(UnauthorizedError):
        verify_init_data("auth_date=1&user=%7B%22id%22%3A1%7D", BOT_TOKEN)


def test_expired_init_data_is_rejected():
    init_data = build_init_data(BOT_TOKEN, USER, auth_date=int(time.time()) - 100_000)
    with pytest.raises(UnauthorizedError):
        verify_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)


async def test_telegram_login_creates_one_user_per_identity(client):
    init_data = build_init_data(BOT_TOKEN, USER)

    first = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert first.status_code == 200, first.text
    assert first.json()["is_new_user"] is True

    second = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert second.status_code == 200
    assert second.json()["is_new_user"] is False

    me_first = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {first.json()['access_token']}"}
    )
    me_second = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {second.json()['access_token']}"}
    )
    assert me_first.json()["id"] == me_second.json()["id"]
    assert me_first.json()["profile"]["username"] == "anna"


async def test_forged_init_data_via_api_is_rejected(client):
    response = await client.post(
        "/api/v1/auth/telegram", json={"init_data": "user=%7B%22id%22%3A1%7D&hash=deadbeef"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_INIT_DATA"


async def test_requests_without_token_are_unauthorized(client):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_garbage_token_is_unauthorized(client):
    response = await client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
