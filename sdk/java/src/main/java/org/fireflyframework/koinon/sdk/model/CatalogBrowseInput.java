// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CatalogBrowseInput contract. */
public record CatalogBrowseInput(
    @JsonProperty("parent_id") JsonField<String> parentId,
    @JsonProperty("workspace_id") JsonField<String> workspaceId,
    @JsonProperty("project_id") JsonField<String> projectId,
    @JsonProperty("kind") JsonField<String> kind,
    @JsonProperty("include_archived") Boolean includeArchived,
    @JsonProperty("view") CatalogBrowseInputView view,
    @JsonProperty("q") String q,
    @JsonProperty("status") JsonField<String> status,
    @JsonProperty("format") JsonField<String> format,
    @JsonProperty("tag") JsonField<String> tag,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("sort") CatalogBrowseInputSort sort,
    @JsonProperty("order") CatalogBrowseInputOrder order,
    @JsonProperty("cursor") JsonField<String> cursor,
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections
) {

    public static CatalogBrowseInput empty(){return new CatalogBrowseInput(null,null,null,null,null,null,null,null,null,null,null,null,null,null,null);}
    public CatalogBrowseInput withParentId(String value){return new CatalogBrowseInput(JsonField.of(value),workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput clearParentId(){return new CatalogBrowseInput(JsonField.clear(),workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput omitParentId(){return new CatalogBrowseInput(null,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withWorkspaceId(String value){return new CatalogBrowseInput(parentId,JsonField.of(value),projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput clearWorkspaceId(){return new CatalogBrowseInput(parentId,JsonField.clear(),projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput omitWorkspaceId(){return new CatalogBrowseInput(parentId,null,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withProjectId(String value){return new CatalogBrowseInput(parentId,workspaceId,JsonField.of(value),kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput clearProjectId(){return new CatalogBrowseInput(parentId,workspaceId,JsonField.clear(),kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput omitProjectId(){return new CatalogBrowseInput(parentId,workspaceId,null,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withKind(String value){return new CatalogBrowseInput(parentId,workspaceId,projectId,JsonField.of(value),includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput clearKind(){return new CatalogBrowseInput(parentId,workspaceId,projectId,JsonField.clear(),includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput omitKind(){return new CatalogBrowseInput(parentId,workspaceId,projectId,null,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withIncludeArchived(Boolean value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,value,view,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withView(CatalogBrowseInputView value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,value,q,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withQ(String value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,value,status,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withStatus(String value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,JsonField.of(value),format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput clearStatus(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,JsonField.clear(),format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput omitStatus(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,null,format,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withFormat(String value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,JsonField.of(value),tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput clearFormat(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,JsonField.clear(),tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput omitFormat(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,null,tag,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withTag(String value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,JsonField.of(value),pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput clearTag(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,JsonField.clear(),pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput omitTag(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,null,pageSize,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withPageSize(Integer value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,value,sort,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withSort(CatalogBrowseInputSort value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,value,order,cursor,readerSourceConnections);}
    public CatalogBrowseInput withOrder(CatalogBrowseInputOrder value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,value,cursor,readerSourceConnections);}
    public CatalogBrowseInput withCursor(String value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,JsonField.of(value),readerSourceConnections);}
    public CatalogBrowseInput clearCursor(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,JsonField.clear(),readerSourceConnections);}
    public CatalogBrowseInput omitCursor(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,null,readerSourceConnections);}
    public CatalogBrowseInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,JsonField.of(value));}
    public CatalogBrowseInput clearReaderSourceConnections(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,JsonField.clear());}
    public CatalogBrowseInput omitReaderSourceConnections(){return new CatalogBrowseInput(parentId,workspaceId,projectId,kind,includeArchived,view,q,status,format,tag,pageSize,sort,order,cursor,null);}
}
