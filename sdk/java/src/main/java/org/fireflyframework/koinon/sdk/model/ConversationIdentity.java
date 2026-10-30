// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ConversationIdentity contract. */
public record ConversationIdentity(
    @JsonProperty("product_name") String productName,
    @JsonProperty("assistant_name") String assistantName,
    @JsonProperty("branding_revision") Integer brandingRevision,
    @JsonProperty("branding_origin") KnowledgeSettingsOrigin brandingOrigin,
    @JsonProperty("branding_sha256") String brandingSha256
) {

}
