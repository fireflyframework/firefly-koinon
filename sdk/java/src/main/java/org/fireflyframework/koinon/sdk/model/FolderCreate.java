// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical FolderCreate contract. */
public record FolderCreate(
    @JsonProperty("name") String name,
    @JsonProperty("parent_id") JsonField<String> parentId,
    @JsonProperty("scope") JsonField<KnowledgeScope> scope
) {

    public static FolderCreate empty(){return new FolderCreate(null,null,null);}
    public FolderCreate withName(String value){return new FolderCreate(value,parentId,scope);}
    public FolderCreate withParentId(String value){return new FolderCreate(name,JsonField.of(value),scope);}
    public FolderCreate clearParentId(){return new FolderCreate(name,JsonField.clear(),scope);}
    public FolderCreate omitParentId(){return new FolderCreate(name,null,scope);}
    public FolderCreate withScope(KnowledgeScope value){return new FolderCreate(name,parentId,JsonField.of(value));}
    public FolderCreate clearScope(){return new FolderCreate(name,parentId,JsonField.clear());}
    public FolderCreate omitScope(){return new FolderCreate(name,parentId,null);}
}
