// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.charset.StandardCharsets;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.Test;

final class CorporateProfileTest {
  private final JsonCodec codec = new JsonCodec();

  @Test
  void partialPresentationDoesNotClearTheOtherPreference() throws Exception {
    var value = OrganizationPresentationInput.empty().withExpectedRevision(3)
        .withAvatarMode(ProfilePresentationMode.PERSONAL);
    var json = codec.tree(codec.encode(value));
    assertEquals(3, json.path("expected_revision").asInt());
    assertEquals("personal", json.path("avatar_mode").asText());
    assertFalse(json.has("name_mode"));
    assertThrows(NoSuchMethodException.class,
        () -> OrganizationPresentationInput.class.getMethod("clearNameMode"));
  }

  @Test
  void mappingPolicyDistinguishesPreserveFromDisable() throws Exception {
    var value = OrganizationProfileMappingInput.empty().withExpectedRevision(2).withEnabled(true);
    assertFalse(codec.tree(codec.encode(value)).has("profile_sync"));
    assertTrue(codec.tree(codec.encode(value.clearProfileSync())).path("profile_sync").isNull());
    assertFalse(codec.tree(codec.encode(value.clearProfileSync().omitProfileSync())).has("profile_sync"));
    assertEquals(2, codec.tree(codec.encode(value.clearProfileSync())).path("expected_revision").asInt());
  }

  @Test
  void refreshHasNoCallerSuppliedUpstreamIdentityAndObservationsAreTyped() throws Exception {
    assertEquals("{}", new String(codec.encode(CorporateProfileRefreshInput.empty()), StandardCharsets.UTF_8));
    assertEquals(0, CorporateProfileRefreshInput.class.getRecordComponents().length);
    CorporateProfileRefresh result = codec.decode(
        "{\"tenant_id\":\"north\",\"status\":\"queued\",\"snapshot_revision\":4}".getBytes(StandardCharsets.UTF_8),
        codec.type(CorporateProfileRefresh.class));
    assertEquals(ProfileSyncStatus.QUEUED, result.status());
    assertEquals(4, result.snapshotRevision());
  }
}
