// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical HistoryBrowseInput contract. */
public record HistoryBrowseInput(
    @JsonProperty("q") String q,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("cursor") JsonField<String> cursor,
    @JsonProperty("status") HistoryBrowseInputStatus status,
    @JsonProperty("folder_id") JsonField<String> folderId,
    @JsonProperty("workspace_id") JsonField<String> workspaceId,
    @JsonProperty("project_id") JsonField<String> projectId,
    @JsonProperty("unfiled") Boolean unfiled,
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections
) {

    public static HistoryBrowseInput empty(){return new HistoryBrowseInput(null,null,null,null,null,null,null,null,null);}
    public HistoryBrowseInput withQ(String value){return new HistoryBrowseInput(value,pageSize,cursor,status,folderId,workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput withPageSize(Integer value){return new HistoryBrowseInput(q,value,cursor,status,folderId,workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput withCursor(String value){return new HistoryBrowseInput(q,pageSize,JsonField.of(value),status,folderId,workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput clearCursor(){return new HistoryBrowseInput(q,pageSize,JsonField.clear(),status,folderId,workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput omitCursor(){return new HistoryBrowseInput(q,pageSize,null,status,folderId,workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput withStatus(HistoryBrowseInputStatus value){return new HistoryBrowseInput(q,pageSize,cursor,value,folderId,workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput withFolderId(String value){return new HistoryBrowseInput(q,pageSize,cursor,status,JsonField.of(value),workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput clearFolderId(){return new HistoryBrowseInput(q,pageSize,cursor,status,JsonField.clear(),workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput omitFolderId(){return new HistoryBrowseInput(q,pageSize,cursor,status,null,workspaceId,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput withWorkspaceId(String value){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,JsonField.of(value),projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput clearWorkspaceId(){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,JsonField.clear(),projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput omitWorkspaceId(){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,null,projectId,unfiled,readerSourceConnections);}
    public HistoryBrowseInput withProjectId(String value){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,workspaceId,JsonField.of(value),unfiled,readerSourceConnections);}
    public HistoryBrowseInput clearProjectId(){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,workspaceId,JsonField.clear(),unfiled,readerSourceConnections);}
    public HistoryBrowseInput omitProjectId(){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,workspaceId,null,unfiled,readerSourceConnections);}
    public HistoryBrowseInput withUnfiled(Boolean value){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,workspaceId,projectId,value,readerSourceConnections);}
    public HistoryBrowseInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,workspaceId,projectId,unfiled,JsonField.of(value));}
    public HistoryBrowseInput clearReaderSourceConnections(){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,workspaceId,projectId,unfiled,JsonField.clear());}
    public HistoryBrowseInput omitReaderSourceConnections(){return new HistoryBrowseInput(q,pageSize,cursor,status,folderId,workspaceId,projectId,unfiled,null);}
}
