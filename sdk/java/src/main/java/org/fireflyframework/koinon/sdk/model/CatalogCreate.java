// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;



/** Typed canonical CatalogCreate contract. */
public record CatalogCreate(
    @JsonProperty("kind") String kind,
    @JsonProperty("name") String name,
    @JsonProperty("parent_id") JsonField<String> parentId,
    @JsonProperty("description") String description,
    @JsonProperty("metadata") JsonNode metadata
) {
    public CatalogCreate {
        metadata=ModelValues.json(metadata);
    }
    @Override public JsonNode metadata(){return ModelValues.json(metadata);}
    public static CatalogCreate empty(){return new CatalogCreate(null,null,null,null,null);}
    public CatalogCreate withKind(String value){return new CatalogCreate(value,name,parentId,description,metadata);}
    public CatalogCreate withName(String value){return new CatalogCreate(kind,value,parentId,description,metadata);}
    public CatalogCreate withParentId(String value){return new CatalogCreate(kind,name,JsonField.of(value),description,metadata);}
    public CatalogCreate clearParentId(){return new CatalogCreate(kind,name,JsonField.clear(),description,metadata);}
    public CatalogCreate omitParentId(){return new CatalogCreate(kind,name,null,description,metadata);}
    public CatalogCreate withDescription(String value){return new CatalogCreate(kind,name,parentId,value,metadata);}
    public CatalogCreate withMetadata(JsonNode value){return new CatalogCreate(kind,name,parentId,description,value);}
}
