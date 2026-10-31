// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical FolderPatch contract. */
public record FolderPatch(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("parent_id") JsonField<String> parentId,
    @JsonProperty("memory_enabled") Boolean memoryEnabled
) {
    public FolderPatch(Long expectedRevision, JsonField<String> name, JsonField<String> parentId){this(expectedRevision,name,parentId,null);}

    public static FolderPatch empty(){return new FolderPatch(null,null,null,null);}
    public FolderPatch withExpectedRevision(Long value){return new FolderPatch(value,name,parentId,memoryEnabled);}
    public FolderPatch withName(String value){return new FolderPatch(expectedRevision,JsonField.of(value),parentId,memoryEnabled);}
    public FolderPatch clearName(){return new FolderPatch(expectedRevision,JsonField.clear(),parentId,memoryEnabled);}
    public FolderPatch omitName(){return new FolderPatch(expectedRevision,null,parentId,memoryEnabled);}
    public FolderPatch withParentId(String value){return new FolderPatch(expectedRevision,name,JsonField.of(value),memoryEnabled);}
    public FolderPatch clearParentId(){return new FolderPatch(expectedRevision,name,JsonField.clear(),memoryEnabled);}
    public FolderPatch omitParentId(){return new FolderPatch(expectedRevision,name,null,memoryEnabled);}
    public FolderPatch withMemoryEnabled(Boolean value){return new FolderPatch(expectedRevision,name,parentId,value);}
}
