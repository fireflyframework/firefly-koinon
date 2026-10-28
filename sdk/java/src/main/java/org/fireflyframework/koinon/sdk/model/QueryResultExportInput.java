// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical QueryResultExportInput contract. */
public record QueryResultExportInput(
    @JsonProperty("kind") QueryResultExportInputKind kind,
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("query_id") String queryId,
    @JsonProperty("format") QueryResultExportInputFormat format,
    @JsonProperty("csv_mode") QueryResultExportInputCsvMode csvMode
) implements ExportReviewRequest {

    public static QueryResultExportInput empty(){return new QueryResultExportInput(null,null,null,null,null);}
    public QueryResultExportInput withKind(QueryResultExportInputKind value){return new QueryResultExportInput(value,datasetId,queryId,format,csvMode);}
    public QueryResultExportInput withDatasetId(String value){return new QueryResultExportInput(kind,value,queryId,format,csvMode);}
    public QueryResultExportInput withQueryId(String value){return new QueryResultExportInput(kind,datasetId,value,format,csvMode);}
    public QueryResultExportInput withFormat(QueryResultExportInputFormat value){return new QueryResultExportInput(kind,datasetId,queryId,value,csvMode);}
    public QueryResultExportInput withCsvMode(QueryResultExportInputCsvMode value){return new QueryResultExportInput(kind,datasetId,queryId,format,value);}
}
