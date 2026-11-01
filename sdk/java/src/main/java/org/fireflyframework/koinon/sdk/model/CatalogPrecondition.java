// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical CatalogPrecondition contract. */
public record CatalogPrecondition(
    @JsonProperty("expected_updated_at") JsonField<Instant> expectedUpdatedAt
) {

    public static CatalogPrecondition empty(){return new CatalogPrecondition(null);}
    public CatalogPrecondition withExpectedUpdatedAt(Instant value){return new CatalogPrecondition(JsonField.of(value));}
    public CatalogPrecondition clearExpectedUpdatedAt(){return new CatalogPrecondition(JsonField.clear());}
    public CatalogPrecondition omitExpectedUpdatedAt(){return new CatalogPrecondition(null);}
}
