// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical BrandingResetInput contract. */
public record BrandingResetInput(
    @JsonProperty("expected_revision") Integer expectedRevision
) {

    public static BrandingResetInput empty(){return new BrandingResetInput(null);}
    public BrandingResetInput withExpectedRevision(Integer value){return new BrandingResetInput(value);}
}
