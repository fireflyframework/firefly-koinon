// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.Test;

final class AnswerReleaseTest {
    @Test
    void serverReleaseIsTypedAndMissingHistoricalReleaseRemainsUnknown() throws Exception {
        var codec = new JsonCodec();
        String release = "{\"run_id\":\"run\",\"message_id\":\"answer\",\"tenant_id\":\"north\","
            + "\"generation_id\":\"generation\",\"publication_sequence\":7,\"outcome\":\"grounded\","
            + "\"version\":1,\"policy_version\":\"knowledge-only-v1\",\"text_sha256\":\"" + "a".repeat(64)
            + "\",\"citations_sha256\":\"" + "b".repeat(64) + "\",\"artifacts_sha256\":\"" + "c".repeat(64)
            + "\",\"policy_sha256\":\"" + "d".repeat(64) + "\",\"fact_ids\":[\"fact\"],"
            + "\"result_pins\":[{\"id\":\"result\",\"sha256\":\"" + "e".repeat(64) + "\"}],"
            + "\"source_refs\":[{\"id\":\"reference\",\"asset_id\":\"document\",\"kind\":\"document\",\"title\":\"Fact\"}],"
            + "\"created_at\":\"2026-11-01T19:00:00.123456Z\"}";
        AnswerAudit audit = codec.decode(("{\"run_id\":\"run\",\"provenance_status\":\"recorded\",\"output_release\":"
            + release + "}").getBytes(StandardCharsets.UTF_8), codec.type(AnswerAudit.class));
        assertEquals(7L, audit.outputRelease().publicationSequence());
        assertEquals(AnswerPolicyOutcome.GROUNDED, audit.outputRelease().outcome());
        assertEquals("result", audit.outputRelease().resultPins().getFirst().id());
        assertEquals("document", audit.outputRelease().sourceRefs().getFirst().assetId());
        assertEquals(Instant.parse("2026-11-01T19:00:00.123456Z"), audit.outputRelease().createdAt());
        assertThrows(UnsupportedOperationException.class, () -> audit.outputRelease().resultPins().clear());
        AnswerAudit old = codec.decode("{\"run_id\":\"old\",\"provenance_status\":\"not_recorded\"}"
            .getBytes(StandardCharsets.UTF_8), codec.type(AnswerAudit.class));
        assertNull(old.outputRelease());
    }

    @Test
    void bothPublishedConstructorsRemainSourceCompatible() {
        var current = new AnswerAudit("run", AnswerAuditProvenanceStatus.RECORDED, null,
            (OrganizationKnowledgeSnapshot) null, (MemoryReceipt) null,
            List.of(), List.of(), List.of(), List.of(), List.of(), null);
        var beforeMemory = new AnswerAudit("run", AnswerAuditProvenanceStatus.RECORDED, null,
            (OrganizationKnowledgeSnapshot) null, List.of(), List.of(), List.of(), List.of(), List.of(), null);
        assertNull(current.outputRelease());
        assertNull(beforeMemory.outputRelease());
        assertNull(beforeMemory.memory());
    }
}
