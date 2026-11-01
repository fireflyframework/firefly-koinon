# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read-only checks of the deployment-owned broker; tenant settings never write realm policy."""

from urllib.parse import quote

from pyfly.container import component
from pyfly.oauth2 import OAuth2Client, OAuth2Endpoints

from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.settings import IdentitySettings
from koinon.security.settings import OidcSettings


@component(name="identity.broker_policy")
class CorporateBrokerPolicy:
    def __init__(self, settings: IdentitySettings, oidc: OidcSettings, directory: NativeCorporateDirectory):
        self.settings, self.oidc, self.directory = settings, oidc, directory

    async def check(self, provider):
        if getattr(provider, "settings_json", {}).get("identity_mode") == "direct":
            matched = (
                provider.kind == "entra"
                and provider.broker_alias is None
                and provider.canonical_issuer == self.oidc.issuer
                and self.oidc.issuer
                == f"https://login.microsoftonline.com/{provider.settings_json.get('tenant_id')}/v2.0"
                and provider.settings_json.get("client_id") == self.oidc.client_id
            )
            return {
                "id": "broker_policy",
                "status": "passed" if matched else "blocked",
                "verified": matched,
                "available": matched,
                "message": "The direct native Entra issuer and client are pinned."
                if matched
                else "Direct Entra must match the native issuer and client.",
            }
        if provider.broker_alias is None:
            return {
                "id": "broker_policy",
                "status": "passed",
                "verified": True,
                "available": True,
                "message": "The existing realm and canonical account remain authoritative.",
            }
        if not self.settings.broker_admin_client_id or not self.settings.broker_admin_secret:
            return {
                "id": "broker_policy",
                "status": "blocked",
                "verified": False,
                "available": None,
                "message": "A deployment administrator must configure read-only broker policy inspection.",
            }
        try:
            origin, realm = self.directory.keycloak_origin(self.oidc.issuer)
            root = f"{origin}/admin/realms/{realm}"
            async with OAuth2Client(
                self.settings.broker_admin_client_id,
                OAuth2Endpoints(self.oidc.issuer + "/protocol/openid-connect/token"),
                client_secret=self.settings.broker_admin_secret,
                timeout=8,
                allow_loopback_http=True,
            ) as oauth:
                token = (await oauth.client_credentials(authentication="client_secret_post")).access_token
            broker = await self.directory._json(
                root + "/identity-provider/instances/" + provider.broker_alias, token
            )
            config = broker.get("config", {})
            if (
                broker.get("enabled") is not True
                or config.get("clientId") != provider.settings_json["client_id"]
            ):
                raise ValueError
            # This initial adapter deliberately accepts the standard OIDC provider representation only.
            # Vendor-specific Keycloak extensions require their own verified representation adapter.
            if provider.kind == "entra":
                expected = f"https://login.microsoftonline.com/{provider.settings_json['tenant_id']}/v2.0"
                if broker.get("providerId") != "oidc" or config.get("issuer") != expected:
                    raise ValueError
            elif provider.kind == "google_workspace":
                if broker.get("providerId") != "google":
                    raise ValueError
            elif (
                broker.get("providerId") != "oidc" or config.get("issuer") != provider.settings_json["issuer"]
            ):
                raise ValueError
            flow_alias = broker.get("firstBrokerLoginFlowAlias")
            if not isinstance(flow_alias, str) or not flow_alias:
                raise ValueError
            executions = await self.directory._json(
                root + "/authentication/flows/" + quote(flow_alias, safe="") + "/executions", token
            )
            enabled = {row.get("providerId") for row in executions if row.get("requirement") != "DISABLED"}
            if "idp-auto-link" in enabled or "idp-username-password-form" not in enabled:
                raise ValueError
            clients = await self.directory._json(
                root + "/clients", token, params={"clientId": self.oidc.client_id}
            )
            if len(clients) != 1 or clients[0].get("clientId") != self.oidc.client_id:
                raise ValueError
            mappers = await self.directory._json(
                root + "/clients/" + clients[0]["id"] + "/protocol-mappers/models", token
            )
            note = next(
                row
                for row in mappers
                if row.get("config", {}).get("claim.name") == "koinon_identity_provider"
            )
            if (
                note.get("protocolMapper") != "oidc-usersessionmodel-note-mapper"
                or note["config"].get("user.session.note") != "identity_provider"
                or note["config"].get("id.token.claim") != "true"
            ):
                raise ValueError
            upstream = await self.directory._json(
                root + "/identity-provider/instances/" + provider.broker_alias + "/mappers", token
            )
            required = {"koinon_external_subject": "sub"}
            if provider.kind == "entra":
                required = {"koinon_external_tid": "tid", "koinon_external_oid": "oid"}
            elif provider.kind == "google_workspace":
                required["koinon_google_hd"] = "hd"
            for claim, upstream_claim in required.items():
                mapping = next(row for row in mappers if row.get("config", {}).get("claim.name") == claim)
                if (
                    mapping.get("protocolMapper") != "oidc-usermodel-attribute-mapper"
                    or mapping["config"].get("id.token.claim") != "true"
                ):
                    raise ValueError
                attribute = mapping["config"].get("user.attribute")
                source = next(
                    row for row in upstream if row.get("config", {}).get("user.attribute") == attribute
                )
                if (
                    source.get("identityProviderMapper") != "oidc-user-attribute-idp-mapper"
                    or source["config"].get("claim") != upstream_claim
                    or source["config"].get("syncMode") != "FORCE"
                ):
                    raise ValueError
            return {
                "id": "broker_policy",
                "status": "passed",
                "verified": True,
                "available": True,
                "message": "Protected upstream claims and explicit existing-account proof were verified.",
            }
        except Exception:
            return {
                "id": "broker_policy",
                "status": "blocked",
                "verified": False,
                "available": None,
                "message": (
                    "Broker policy is unverified. Review upstream identity claims and account-linking "
                    "flow with a deployment administrator."
                ),
            }
