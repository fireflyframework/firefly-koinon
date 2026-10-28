# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from koinon_sdk import KoinonClient, ProfileUpdate

PROFILE = {
    "subject": "issuer|self",
    "display_name": "Researcher",
    "locale": "es-MX",
    "time_zone": "UTC",
    "response_language": "es",
}


async def test_profile_methods_keep_identity_server_owned_and_images_binary():
    seen = []

    def handle(request):
        seen.append(request)
        if request.method == "GET" and request.url.path.endswith("/avatar"):
            return httpx.Response(200, content=b"controlled-jpeg", headers={"Content-Type": "image/jpeg"})
        if request.method == "POST":
            assert request.content == b"controlled-png" and request.headers["Content-Type"] == "image/png"
        return httpx.Response(200, json=PROFILE)

    async with KoinonClient(
        "https://api.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        assert (await client.profile()).subject == "issuer|self"
        await client.update_profile(ProfileUpdate(display_name="Researcher"))
        await client.set_avatar(b"controlled-png", media_type="image/png")
        assert await client.avatar() == b"controlled-jpeg"
        await client.delete_avatar()
    assert [request.method for request in seen] == ["GET", "PATCH", "POST", "GET", "DELETE"]
    assert all(request.headers["Authorization"] == "Bearer fresh" for request in seen)
    with pytest.raises(ValueError):
        ProfileUpdate(subject="issuer|other")
