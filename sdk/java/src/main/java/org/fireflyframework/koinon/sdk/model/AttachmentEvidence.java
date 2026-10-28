// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AttachmentEvidence contract. */
public record AttachmentEvidence(
    @JsonProperty("attachments") List<AttachmentEvidenceItem> attachments
) {
    public AttachmentEvidence {
        attachments=attachments==null?null:List.copyOf(attachments);
    }

}
