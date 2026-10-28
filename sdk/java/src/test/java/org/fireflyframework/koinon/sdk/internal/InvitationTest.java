// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.*;

import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.Test;

final class InvitationTest {
  @Test
  void tokenReprIsRedactedButWireIsExactAndNullScopeSurvives() throws Exception {
    var codec = new JsonCodec();
    var secret = "private-one-time-invitation";
    var token = InvitationToken.empty().withToken(secret);
    assertFalse(token.toString().contains(secret));
    assertFalse(new InvitationCreated(null, secret).toString().contains(secret));
    assertEquals(secret, codec.tree(codec.encode(token)).path("token").asText());
    var input = InvitationInput.empty().withRole(MembershipRole.VIEWER).clearWorkspaceId();
    var wire = codec.tree(codec.encode(input));
    assertTrue(wire.path("workspace_id").isNull());
    assertFalse(wire.has("expires_in_hours"));
    var options =
        MembershipFilter.empty()
            .withScope(MembershipScope.TENANT)
            .withRole(MembershipRole.VIEWER)
            .withPage(2)
            .applyTo(RequestOptions.defaults());
    assertEquals("tenant", options.query().get("scope"));
    assertEquals("viewer", options.query().get("role"));
  }
}
