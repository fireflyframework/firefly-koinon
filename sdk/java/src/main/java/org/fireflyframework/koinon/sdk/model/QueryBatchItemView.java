// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical QueryBatchItemView contract. */
public record QueryBatchItemView(
    @JsonProperty("id") String id,
    @JsonProperty("client_item_id") String clientItemId,
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("question") String question,
    @JsonProperty("status") QueryBatchItemViewStatus status,
    @JsonProperty("job_id") String jobId,
    @JsonProperty("error_code") String errorCode,
    @JsonProperty("query_id") String queryId
) {

}
