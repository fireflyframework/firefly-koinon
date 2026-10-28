// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;



/** Typed canonical CatalogUpdate contract. */
public record CatalogUpdate(
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("description") JsonField<String> description,
    @JsonProperty("metadata") JsonField<JsonNode> metadata
) {

    public static CatalogUpdate empty(){return new CatalogUpdate(null,null,null);}
    public CatalogUpdate withName(String value){return new CatalogUpdate(JsonField.of(value),description,metadata);}
    public CatalogUpdate clearName(){return new CatalogUpdate(JsonField.clear(),description,metadata);}
    public CatalogUpdate omitName(){return new CatalogUpdate(null,description,metadata);}
    public CatalogUpdate withDescription(String value){return new CatalogUpdate(name,JsonField.of(value),metadata);}
    public CatalogUpdate clearDescription(){return new CatalogUpdate(name,JsonField.clear(),metadata);}
    public CatalogUpdate omitDescription(){return new CatalogUpdate(name,null,metadata);}
    public CatalogUpdate withMetadata(JsonNode value){return new CatalogUpdate(name,description,JsonField.of(value));}
    public CatalogUpdate clearMetadata(){return new CatalogUpdate(name,description,JsonField.clear());}
    public CatalogUpdate omitMetadata(){return new CatalogUpdate(name,description,null);}
}
