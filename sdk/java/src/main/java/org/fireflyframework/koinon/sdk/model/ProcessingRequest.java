// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ProcessingRequest contract. */
public record ProcessingRequest(
    @JsonProperty("page") Integer page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("workspace_id") JsonField<String> workspaceId
) {

    public static ProcessingRequest empty(){return new ProcessingRequest(null,null,null);}
    public ProcessingRequest withPage(Integer value){return new ProcessingRequest(value,pageSize,workspaceId);}
    public ProcessingRequest withPageSize(Integer value){return new ProcessingRequest(page,value,workspaceId);}
    public ProcessingRequest withWorkspaceId(String value){return new ProcessingRequest(page,pageSize,JsonField.of(value));}
    public ProcessingRequest clearWorkspaceId(){return new ProcessingRequest(page,pageSize,JsonField.clear());}
    public ProcessingRequest omitWorkspaceId(){return new ProcessingRequest(page,pageSize,null);}
}
