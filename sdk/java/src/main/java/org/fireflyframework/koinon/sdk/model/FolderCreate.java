// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical FolderCreate contract. */
public record FolderCreate(
    @JsonProperty("name") String name,
    @JsonProperty("parent_id") JsonField<String> parentId,
    @JsonProperty("scope") JsonField<KnowledgeScope> scope,
    @JsonProperty("memory_enabled") Boolean memoryEnabled
) {
    public FolderCreate(String name, JsonField<String> parentId, JsonField<KnowledgeScope> scope){this(name,parentId,scope,null);}

    public static FolderCreate empty(){return new FolderCreate(null,null,null,null);}
    public FolderCreate withName(String value){return new FolderCreate(value,parentId,scope,memoryEnabled);}
    public FolderCreate withParentId(String value){return new FolderCreate(name,JsonField.of(value),scope,memoryEnabled);}
    public FolderCreate clearParentId(){return new FolderCreate(name,JsonField.clear(),scope,memoryEnabled);}
    public FolderCreate omitParentId(){return new FolderCreate(name,null,scope,memoryEnabled);}
    public FolderCreate withScope(KnowledgeScope value){return new FolderCreate(name,parentId,JsonField.of(value),memoryEnabled);}
    public FolderCreate clearScope(){return new FolderCreate(name,parentId,JsonField.clear(),memoryEnabled);}
    public FolderCreate omitScope(){return new FolderCreate(name,parentId,null,memoryEnabled);}
    public FolderCreate withMemoryEnabled(Boolean value){return new FolderCreate(name,parentId,scope,value);}
}
