// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ProcessingRequest contract. */
public record ProcessingRequest(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("page") Integer page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("workspace_id") JsonField<String> workspaceId
) {

    public static ProcessingRequest empty(){return new ProcessingRequest(null,null,null,null);}
    public ProcessingRequest withReaderSourceConnections(List<ReaderSourceSelection> value){return new ProcessingRequest(JsonField.of(value),page,pageSize,workspaceId);}
    public ProcessingRequest clearReaderSourceConnections(){return new ProcessingRequest(JsonField.clear(),page,pageSize,workspaceId);}
    public ProcessingRequest omitReaderSourceConnections(){return new ProcessingRequest(null,page,pageSize,workspaceId);}
    public ProcessingRequest withPage(Integer value){return new ProcessingRequest(readerSourceConnections,value,pageSize,workspaceId);}
    public ProcessingRequest withPageSize(Integer value){return new ProcessingRequest(readerSourceConnections,page,value,workspaceId);}
    public ProcessingRequest withWorkspaceId(String value){return new ProcessingRequest(readerSourceConnections,page,pageSize,JsonField.of(value));}
    public ProcessingRequest clearWorkspaceId(){return new ProcessingRequest(readerSourceConnections,page,pageSize,JsonField.clear());}
    public ProcessingRequest omitWorkspaceId(){return new ProcessingRequest(readerSourceConnections,page,pageSize,null);}
}
