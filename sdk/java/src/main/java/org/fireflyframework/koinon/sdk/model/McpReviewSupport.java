// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical McpReviewSupport contract. */
public record McpReviewSupport(
    @JsonProperty("supported") Boolean supported,
    @JsonProperty("mechanism") McpReviewSupportMechanism mechanism,
    @JsonProperty("resource_uri") McpReviewSupportResourceUri resourceUri,
    @JsonProperty("mime_type") McpReviewSupportMimeType mimeType,
    @JsonProperty("external_redirect") Boolean externalRedirect,
    @JsonProperty("client_support") McpReviewSupportClientSupport clientSupport
) {

}
