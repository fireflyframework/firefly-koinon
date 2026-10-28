# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Render the local-only realm with credentials supplied privately through environment."""

import argparse
import json
import os
from pathlib import Path

USERS = {
    "admin": "8c85d9a1-6168-4fb0-ae11-1b8a41227a01",
    "analyst": "8c85d9a1-6168-4fb0-ae11-1b8a41227a02",
    "editor": "8c85d9a1-6168-4fb0-ae11-1b8a41227a03",
    "viewer": "8c85d9a1-6168-4fb0-ae11-1b8a41227a04",
    "outsider": "8c85d9a1-6168-4fb0-ae11-1b8a41227a05",
}


def realm(password: str, client_secret: str) -> dict:
    if len(password) < 16 or len(client_secret) < 24:
        raise ValueError(
            "Use generated local credentials of at least 16 and 24 characters"
        )
    return {
        "realm": "koinon",
        "enabled": True,
        "sslRequired": "external",
        "registrationAllowed": False,
        "resetPasswordAllowed": False,
        "rememberMe": False,
        "bruteForceProtected": True,
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 28800,
        "clients": [
            {
                "clientId": "koinon-browser",
                "name": "firefly koinon local browser",
                "enabled": True,
                "protocol": "openid-connect",
                "publicClient": False,
                "secret": client_secret,
                "standardFlowEnabled": True,
                "directAccessGrantsEnabled": False,
                "serviceAccountsEnabled": False,
                "redirectUris": ["http://127.0.0.1:18781/login/oauth2/code/koinon"],
                "webOrigins": ["http://127.0.0.1:18782"],
                "attributes": {"pkce.code.challenge.method": "S256"},
                "protocolMappers": [
                    {
                        "name": "koinon-api-audience",
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-audience-mapper",
                        "consentRequired": False,
                        "config": {
                            "included.client.audience": "koinon-api",
                            "id.token.claim": "false",
                            "access.token.claim": "true",
                        },
                    }
                ],
            },
            {
                "clientId": "koinon-api",
                "enabled": True,
                "protocol": "openid-connect",
                "bearerOnly": True,
                "standardFlowEnabled": False,
                "directAccessGrantsEnabled": False,
            },
        ],
        "users": [
            {
                "id": identifier,
                "username": name,
                "enabled": True,
                "emailVerified": True,
                "email": f"{name}@koinon.example",
                "firstName": name.title(),
                "lastName": "Local fixture",
                "credentials": [
                    {"type": "password", "value": password, "temporary": False}
                ],
            }
            for name, identifier in USERS.items()
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="Private runtime import JSON path; never commit it"
    )
    args = parser.parse_args()
    body = realm(
        os.environ["KOINON_DEMO_PASSWORD"], os.environ["KOINON_OIDC_CLIENT_SECRET"]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(body, target, indent=2)
        target.write("\n")
    print(f"Rendered local realm to {args.output}; generated secrets were not printed")


if __name__ == "__main__":
    main()
