// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.util.List;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.model.SearchHit;
import org.fireflyframework.koinon.sdk.model.SourceReference;
import org.fireflyframework.koinon.sdk.model.SourceReferencePageBasis;
import org.junit.jupiter.api.Test;

final class DocumentHistoryTest {
    @Test
    void legacySearchHitsKeepTheirConstructorAndAcceptMissingReferenceOnTheWire() throws Exception {
        var legacy = new SearchHit("projection", "Recorded", "retained", "document", null, null, List.of());
        assertNull(legacy.sourceReference());
        var codec = new JsonCodec();
        SearchHit decoded = codec.decode("{\"id\":\"projection\",\"title\":\"Recorded\",\"text\":\"retained\",\"asset_id\":\"document\"}".getBytes(java.nio.charset.StandardCharsets.UTF_8), codec.type(SearchHit.class));
        assertNull(decoded.sourceReference());
    }

    @Test
    void searchHitRetainsItsTypedImmutableReference() throws Exception {
        assertEquals(SourceReference.class, SearchHit.class.getMethod("sourceReference").getReturnType());
    }

    @Test
    void documentHistoryModelsPreserveThePublishedSourceReferencePageBasisType() throws Exception {
        assertEquals(SourceReferencePageBasis.class, SourceReference.class.getMethod("pageBasis").getReturnType());
    }
}
