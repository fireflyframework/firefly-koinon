// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical DeliveryObservationPage contract. */
public record DeliveryObservationPage(
    @JsonProperty("items") List<DeliveryOperationObservation> items,
    @JsonProperty("has_more") Boolean hasMore
) {
    public DeliveryObservationPage {
        items=items==null?null:List.copyOf(items);
    }

}
