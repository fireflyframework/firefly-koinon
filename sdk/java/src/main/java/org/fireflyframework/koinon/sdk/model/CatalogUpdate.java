// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;



/** Typed canonical CatalogUpdate contract. */
public record CatalogUpdate(
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("description") JsonField<String> description,
    @JsonProperty("metadata") JsonField<JsonNode> metadata,
    @JsonProperty("expected_updated_at") JsonField<Instant> expectedUpdatedAt
) {
    public CatalogUpdate(JsonField<String> name, JsonField<String> description, JsonField<JsonNode> metadata){this(name,description,metadata,null);}

    public static CatalogUpdate empty(){return new CatalogUpdate(null,null,null,null);}
    public CatalogUpdate withName(String value){return new CatalogUpdate(JsonField.of(value),description,metadata,expectedUpdatedAt);}
    public CatalogUpdate clearName(){return new CatalogUpdate(JsonField.clear(),description,metadata,expectedUpdatedAt);}
    public CatalogUpdate omitName(){return new CatalogUpdate(null,description,metadata,expectedUpdatedAt);}
    public CatalogUpdate withDescription(String value){return new CatalogUpdate(name,JsonField.of(value),metadata,expectedUpdatedAt);}
    public CatalogUpdate clearDescription(){return new CatalogUpdate(name,JsonField.clear(),metadata,expectedUpdatedAt);}
    public CatalogUpdate omitDescription(){return new CatalogUpdate(name,null,metadata,expectedUpdatedAt);}
    public CatalogUpdate withMetadata(JsonNode value){return new CatalogUpdate(name,description,JsonField.of(value),expectedUpdatedAt);}
    public CatalogUpdate clearMetadata(){return new CatalogUpdate(name,description,JsonField.clear(),expectedUpdatedAt);}
    public CatalogUpdate omitMetadata(){return new CatalogUpdate(name,description,null,expectedUpdatedAt);}
    public CatalogUpdate withExpectedUpdatedAt(Instant value){return new CatalogUpdate(name,description,metadata,JsonField.of(value));}
    public CatalogUpdate clearExpectedUpdatedAt(){return new CatalogUpdate(name,description,metadata,JsonField.clear());}
    public CatalogUpdate omitExpectedUpdatedAt(){return new CatalogUpdate(name,description,metadata,null);}
}
