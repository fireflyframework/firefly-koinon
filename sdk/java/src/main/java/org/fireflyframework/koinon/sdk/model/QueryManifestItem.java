// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical QueryManifestItem contract. */
public record QueryManifestItem(
    @JsonProperty("client_item_id") String clientItemId,
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("question") String question
) {

    public static QueryManifestItem empty(){return new QueryManifestItem(null,null,null);}
    public QueryManifestItem withClientItemId(String value){return new QueryManifestItem(value,datasetId,question);}
    public QueryManifestItem withDatasetId(String value){return new QueryManifestItem(clientItemId,value,question);}
    public QueryManifestItem withQuestion(String value){return new QueryManifestItem(clientItemId,datasetId,value);}
}
