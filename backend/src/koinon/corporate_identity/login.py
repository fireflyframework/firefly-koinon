# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import bean, configuration
from pyfly.kernel import SecurityException
from pyfly.security.context import SecurityContext
from pyfly.security.oauth2 import OAuth2AuthenticationSuccessHandler, OAuth2AuthorizationRequestCustomizer

from koinon.corporate_identity.challenges import CorporateLoginChallenges
from koinon.corporate_identity.presentation import CorporatePresentation
from koinon.corporate_identity.refresh import CorporateAccessRefresh
from koinon.organization_people.service import OrganizationPeopleService
from koinon.profiles.service import ProfileService


class CorporateLoginCustomizer(OAuth2AuthorizationRequestCustomizer):
    def __init__(self, challenges: CorporateLoginChallenges):
        self.challenges = challenges

    async def customize(self, request, registration):
        session = request.state.session
        session.remove_attribute("koinon_identity_test")
        identifier = request.query_params.get("identity_test")
        if identifier is None:
            return {}
        context = session.get_attribute("SECURITY_CONTEXT")
        if (
            not isinstance(context, SecurityContext)
            or not context.is_authenticated
            or not context.attributes.get("iss")
            or context.attributes.get("sub") != context.user_id
            or not 1 <= len(identifier) <= 64
        ):
            raise SecurityException(
                "Sign in as an organization administrator before testing corporate access.",
                code="IDENTITY_TEST_SESSION_REQUIRED",
            )
        provider = await self.challenges.begin_authorization(
            identifier, f"{context.attributes['iss']}|{context.user_id}"
        )
        session.set_attribute("koinon_identity_test", identifier)
        parameters = {"prompt": "login", "max_age": "0"}
        if provider.broker_alias:
            parameters["kc_idp_hint"] = provider.broker_alias
        return parameters


class CorporateLoginSuccess(OAuth2AuthenticationSuccessHandler):
    def __init__(
        self,
        challenges: CorporateLoginChallenges,
        refresh: CorporateAccessRefresh,
        profiles: ProfileService,
        presentation: CorporatePresentation | None = None,
        organization_people: OrganizationPeopleService | None = None,
    ):
        self.organization_people = organization_people
        self.challenges, self.refresh, self.profiles, self.presentation = (
            challenges,
            refresh,
            profiles,
            presentation,
        )

    async def on_success(self, request, registration, context):
        identifier = request.state.session.get_attribute("koinon_identity_test")
        request.state.session.remove_attribute("koinon_identity_test")
        if identifier:
            await self.challenges.complete(identifier, context)
        await self.refresh.login(context)
        if self.presentation is not None:
            await self.presentation.initialize(context)
        else:
            await self.profiles.get(f"{context.attributes['iss']}|{context.user_id}", context.attributes)
        if self.organization_people is not None:
            await self.organization_people.observe_login(context)


@configuration
class CorporateLoginConfiguration:
    @bean(name="identity.authorization_customizer")
    def customizer(self, challenges: CorporateLoginChallenges) -> OAuth2AuthorizationRequestCustomizer:
        return CorporateLoginCustomizer(challenges)

    @bean(name="identity.authentication_success")
    def success(
        self,
        challenges: CorporateLoginChallenges,
        refresh: CorporateAccessRefresh,
        profiles: ProfileService,
        presentation: CorporatePresentation,
        organization_people: OrganizationPeopleService | None = None,
    ) -> OAuth2AuthenticationSuccessHandler:
        return CorporateLoginSuccess(challenges, refresh, profiles, presentation, organization_people)
