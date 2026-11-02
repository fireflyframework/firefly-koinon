// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import org.fireflyframework.koinon.sdk.model.McpReviewSupport;
import org.fireflyframework.koinon.sdk.model.McpReviewSupportClientSupport;
import org.fireflyframework.koinon.sdk.model.ModelActivityCounts;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

final class CommunicationsRecoveryTest {
    @Test void addingRecoveryRecipientStatesPreservesExistingPublicEnumTypes() throws Exception {
        assertEquals(McpReviewSupportClientSupport.class, McpReviewSupport.class.getMethod("clientSupport").getReturnType());
        assertEquals(McpReviewSupportClientSupport.class, ModelActivityCounts.class.getMethod("externalClientConsumption").getReturnType());
    }
}
