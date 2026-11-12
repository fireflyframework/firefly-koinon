// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical QueryRequest contract. */
public record QueryRequest(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("question") String question,
    @JsonProperty("conversation_id") JsonField<String> conversationId,
    @JsonProperty("sql") JsonField<String> sql
) {

    public static QueryRequest empty(){return new QueryRequest(null,null,null,null,null);}
    public QueryRequest withReaderSourceConnections(List<ReaderSourceSelection> value){return new QueryRequest(JsonField.of(value),datasetId,question,conversationId,sql);}
    public QueryRequest clearReaderSourceConnections(){return new QueryRequest(JsonField.clear(),datasetId,question,conversationId,sql);}
    public QueryRequest omitReaderSourceConnections(){return new QueryRequest(null,datasetId,question,conversationId,sql);}
    public QueryRequest withDatasetId(String value){return new QueryRequest(readerSourceConnections,value,question,conversationId,sql);}
    public QueryRequest withQuestion(String value){return new QueryRequest(readerSourceConnections,datasetId,value,conversationId,sql);}
    public QueryRequest withConversationId(String value){return new QueryRequest(readerSourceConnections,datasetId,question,JsonField.of(value),sql);}
    public QueryRequest clearConversationId(){return new QueryRequest(readerSourceConnections,datasetId,question,JsonField.clear(),sql);}
    public QueryRequest omitConversationId(){return new QueryRequest(readerSourceConnections,datasetId,question,null,sql);}
    public QueryRequest withSql(String value){return new QueryRequest(readerSourceConnections,datasetId,question,conversationId,JsonField.of(value));}
    public QueryRequest clearSql(){return new QueryRequest(readerSourceConnections,datasetId,question,conversationId,JsonField.clear());}
    public QueryRequest omitSql(){return new QueryRequest(readerSourceConnections,datasetId,question,conversationId,null);}
}
