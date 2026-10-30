// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.model.OrganizationPerson;
import org.fireflyframework.koinon.sdk.model.OrganizationPersonPatch;
import org.fireflyframework.koinon.sdk.model.OrganizationUnitKind;
import org.fireflyframework.koinon.sdk.model.OrganizationUnitSummary;
import org.junit.jupiter.api.Test;

final class OrganizationDirectoryTest {
  @Test
  void unassignedPeopleKeepTheirNullableIdentityAndTypedSource() throws Exception {
    var codec = new JsonCodec();
    OrganizationPerson value = codec.decode(
        "{\"id\":null,\"display_name\":\"Alex Morgan\",\"revision\":0,\"source\":\"unassigned\"}"
            .getBytes(StandardCharsets.UTF_8),
        codec.type(OrganizationPerson.class));
    assertNull(value.id());
    assertEquals(0, value.revision());
    assertEquals("unassigned", value.source().value());
    assertThrows(NoSuchMethodException.class, () -> OrganizationPerson.class.getMethod("subject"));
  }

  @Test
  void explicitRelationshipClearRetainsItsRevisionAndDoesNotInventRoleFields() throws Exception {
    var codec = new JsonCodec();
    var value = OrganizationPersonPatch.empty().withExpectedRevision(4).clearManagerId();
    var json = new String(codec.encode(value), StandardCharsets.UTF_8);
    assertTrue(json.contains("\"manager_id\":null"));
    assertTrue(json.contains("\"expected_revision\":4"));
    assertFalse(json.contains("job_title"));
    assertThrows(NoSuchMethodException.class, () -> OrganizationPersonPatch.class.getMethod("roles"));
  }

  @Test
  void unitKindsArePublicTypedEnums() throws Exception {
    assertEquals(OrganizationUnitKind.class, OrganizationUnitSummary.class.getMethod("kind").getReturnType());
  }
}
