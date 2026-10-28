// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IndexPlanInput contract. */
public record IndexPlanInput(
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("domain") KnowledgeDomain domain,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("expected_dimensions") JsonField<Integer> expectedDimensions
) {

    public static IndexPlanInput empty(){return new IndexPlanInput(null,null,null,null,null);}
    public IndexPlanInput withWorkspaceId(String value){return new IndexPlanInput(value,domain,providerId,modelId,expectedDimensions);}
    public IndexPlanInput withDomain(KnowledgeDomain value){return new IndexPlanInput(workspaceId,value,providerId,modelId,expectedDimensions);}
    public IndexPlanInput withProviderId(String value){return new IndexPlanInput(workspaceId,domain,value,modelId,expectedDimensions);}
    public IndexPlanInput withModelId(String value){return new IndexPlanInput(workspaceId,domain,providerId,value,expectedDimensions);}
    public IndexPlanInput withExpectedDimensions(Integer value){return new IndexPlanInput(workspaceId,domain,providerId,modelId,JsonField.of(value));}
    public IndexPlanInput clearExpectedDimensions(){return new IndexPlanInput(workspaceId,domain,providerId,modelId,JsonField.clear());}
    public IndexPlanInput omitExpectedDimensions(){return new IndexPlanInput(workspaceId,domain,providerId,modelId,null);}
}
