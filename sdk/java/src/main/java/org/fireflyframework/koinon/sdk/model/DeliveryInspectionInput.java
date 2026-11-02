// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DeliveryInspectionInput contract. */
public record DeliveryInspectionInput(
    @JsonProperty("expected_generation") Long expectedGeneration
) {

    public static DeliveryInspectionInput empty(){return new DeliveryInspectionInput(null);}
    public DeliveryInspectionInput withExpectedGeneration(Long value){return new DeliveryInspectionInput(value);}
}
