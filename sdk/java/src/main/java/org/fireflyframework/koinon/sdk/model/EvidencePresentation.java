// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical EvidencePresentation contract. */
public record EvidencePresentation(
    @JsonProperty("locale") String locale,
    @JsonProperty("time_zone") String timeZone,
    @JsonProperty("response_language") String responseLanguage
) {

}
