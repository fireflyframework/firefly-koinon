// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical TitleSuggestion contract. */
public record TitleSuggestion(
    @JsonProperty("title") String title,
    @JsonProperty("based_on_revision") Long basedOnRevision
) {

}
