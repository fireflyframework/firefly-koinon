// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AttachmentRevision contract. */
public record AttachmentRevision(
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static AttachmentRevision empty(){return new AttachmentRevision(null);}
    public AttachmentRevision withExpectedRevision(Long value){return new AttachmentRevision(value);}
}
