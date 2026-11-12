// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceAuthorizationInput contract. */
public record SourceAuthorizationInput(
    @JsonProperty("provider") ReaderSourceSelectionProvider provider
) {

    public static SourceAuthorizationInput empty(){return new SourceAuthorizationInput(null);}
    public SourceAuthorizationInput withProvider(ReaderSourceSelectionProvider value){return new SourceAuthorizationInput(value);}
}
