// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeConnectionInput contract. */
public record KnowledgeConnectionInput(
    @JsonProperty("domain") KnowledgeDomain domain,
    @JsonProperty("role") String role,
    @JsonProperty("workspace_id") JsonField<String> workspaceId,
    @JsonProperty("mode") ConnectionMode mode,
    @JsonProperty("provider_id") JsonField<String> providerId,
    @JsonProperty("model_id") JsonField<String> modelId,
    @JsonProperty("model_options") JsonField<ModelParameters> modelOptions,
    @JsonProperty("dimensions") JsonField<Long> dimensions,
    @JsonProperty("storage_dimensions") JsonField<Long> storageDimensions,
    @JsonProperty("space_id") JsonField<String> spaceId,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("expected_revision") JsonField<Long> expectedRevision
) {

    public static KnowledgeConnectionInput empty(){return new KnowledgeConnectionInput(null,null,null,null,null,null,null,null,null,null,null,null);}
    public KnowledgeConnectionInput withDomain(KnowledgeDomain value){return new KnowledgeConnectionInput(value,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withRole(String value){return new KnowledgeConnectionInput(domain,value,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withWorkspaceId(String value){return new KnowledgeConnectionInput(domain,role,JsonField.of(value),mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput clearWorkspaceId(){return new KnowledgeConnectionInput(domain,role,JsonField.clear(),mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput omitWorkspaceId(){return new KnowledgeConnectionInput(domain,role,null,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withMode(ConnectionMode value){return new KnowledgeConnectionInput(domain,role,workspaceId,value,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withProviderId(String value){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,JsonField.of(value),modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput clearProviderId(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,JsonField.clear(),modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput omitProviderId(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,null,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withModelId(String value){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,JsonField.of(value),modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput clearModelId(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,JsonField.clear(),modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput omitModelId(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,null,modelOptions,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withModelOptions(ModelParameters value){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,JsonField.of(value),dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput clearModelOptions(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,JsonField.clear(),dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput omitModelOptions(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,null,dimensions,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withDimensions(Long value){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,JsonField.of(value),storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput clearDimensions(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,JsonField.clear(),storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput omitDimensions(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,null,storageDimensions,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withStorageDimensions(Long value){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,JsonField.of(value),spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput clearStorageDimensions(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,JsonField.clear(),spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput omitStorageDimensions(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,null,spaceId,enabled,expectedRevision);}
    public KnowledgeConnectionInput withSpaceId(String value){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,JsonField.of(value),enabled,expectedRevision);}
    public KnowledgeConnectionInput clearSpaceId(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,JsonField.clear(),enabled,expectedRevision);}
    public KnowledgeConnectionInput omitSpaceId(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,null,enabled,expectedRevision);}
    public KnowledgeConnectionInput withEnabled(Boolean value){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,value,expectedRevision);}
    public KnowledgeConnectionInput withExpectedRevision(Long value){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,JsonField.of(value));}
    public KnowledgeConnectionInput clearExpectedRevision(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,JsonField.clear());}
    public KnowledgeConnectionInput omitExpectedRevision(){return new KnowledgeConnectionInput(domain,role,workspaceId,mode,providerId,modelId,modelOptions,dimensions,storageDimensions,spaceId,enabled,null);}
}
