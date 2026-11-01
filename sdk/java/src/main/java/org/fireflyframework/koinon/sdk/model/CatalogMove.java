// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical CatalogMove contract. */
public record CatalogMove(
    @JsonProperty("parent_id") String parentId,
    @JsonProperty("expected_parent_id") String expectedParentId,
    @JsonProperty("expected_updated_at") Instant expectedUpdatedAt
) {

    public static CatalogMove empty(){return new CatalogMove(null,null,null);}
    public CatalogMove withParentId(String value){return new CatalogMove(value,expectedParentId,expectedUpdatedAt);}
    public CatalogMove withExpectedParentId(String value){return new CatalogMove(parentId,value,expectedUpdatedAt);}
    public CatalogMove withExpectedUpdatedAt(Instant value){return new CatalogMove(parentId,expectedParentId,value);}
}
