// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical QueryRequest contract. */
public record QueryRequest(
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("question") String question,
    @JsonProperty("conversation_id") JsonField<String> conversationId,
    @JsonProperty("sql") JsonField<String> sql
) {

    public static QueryRequest empty(){return new QueryRequest(null,null,null,null);}
    public QueryRequest withDatasetId(String value){return new QueryRequest(value,question,conversationId,sql);}
    public QueryRequest withQuestion(String value){return new QueryRequest(datasetId,value,conversationId,sql);}
    public QueryRequest withConversationId(String value){return new QueryRequest(datasetId,question,JsonField.of(value),sql);}
    public QueryRequest clearConversationId(){return new QueryRequest(datasetId,question,JsonField.clear(),sql);}
    public QueryRequest omitConversationId(){return new QueryRequest(datasetId,question,null,sql);}
    public QueryRequest withSql(String value){return new QueryRequest(datasetId,question,conversationId,JsonField.of(value));}
    public QueryRequest clearSql(){return new QueryRequest(datasetId,question,conversationId,JsonField.clear());}
    public QueryRequest omitSql(){return new QueryRequest(datasetId,question,conversationId,null);}
}
