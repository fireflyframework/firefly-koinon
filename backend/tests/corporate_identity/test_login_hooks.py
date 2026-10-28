# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from pyfly.kernel import SecurityException
from pyfly.security.context import SecurityContext
from pyfly.session.session import HttpSession
from starlette.requests import Request

from koinon.corporate_identity.login import CorporateLoginCustomizer, CorporateLoginSuccess


def request(session, query=""):
    value = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/oauth2/authorization/koinon",
            "headers": [],
            "query_string": query.encode(),
        }
    )
    value.state.session = session
    return value


async def test_challenge_is_bound_to_existing_session_and_uses_native_freshness_parameters():
    observed = []

    class Challenges:
        async def begin_authorization(self, identifier, subject):
            observed.append((identifier, subject))
            return SimpleNamespace(broker_alias="north-entra")

    hook = CorporateLoginCustomizer(Challenges())
    session = HttpSession("existing-admin")
    session.set_attribute(
        "SECURITY_CONTEXT",
        SecurityContext(user_id="existing", attributes={"iss": "https://identity.test", "sub": "existing"}),
    )
    parameters = await hook.customize(request(session, "identity_test=opaque-id"), None)
    assert parameters == {"kc_idp_hint": "north-entra", "prompt": "login", "max_age": "0"}
    assert observed == [("opaque-id", "https://identity.test|existing")]
    assert session.get_attribute("koinon_identity_test") == "opaque-id"
    assert await hook.customize(request(session), None) == {}
    assert session.get_attribute("koinon_identity_test") is None
    with pytest.raises(SecurityException):
        await hook.customize(request(HttpSession("anonymous"), "identity_test=opaque-id"), None)


async def test_success_consumes_challenge_before_profile_and_managed_access_without_changing_subject():
    calls = []

    class Challenges:
        async def complete(self, identifier, context):
            calls.append(("proof", identifier, context.user_id))

    class Reconcile:
        async def login(self, context):
            calls.append(("managed", context.user_id))

    class Profiles:
        async def get(self, subject, verified):
            calls.append(("profile", subject, verified["name"]))

    hook = CorporateLoginSuccess(Challenges(), Reconcile(), Profiles())
    session = HttpSession("existing-admin")
    session.set_attribute("koinon_identity_test", "opaque-id")
    context = SecurityContext(
        user_id="existing",
        attributes={"iss": "https://identity.test", "sub": "existing", "name": "Existing person"},
    )
    await hook.on_success(request(session), None, context)
    assert calls == [
        ("proof", "opaque-id", "existing"),
        ("managed", "existing"),
        ("profile", "https://identity.test|existing", "Existing person"),
    ]
    assert session.get_attribute("koinon_identity_test") is None and context.user_id == "existing"
