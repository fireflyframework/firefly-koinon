// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ExternalFileReviewInput contract. */
public record ExternalFileReviewInput(
    @JsonProperty("filename") String filename,
    @JsonProperty("content_type") JsonField<String> contentType,
    @JsonProperty("mode") AddKnowledgeMode mode,
    @JsonProperty("destination_id") String destinationId,
    @JsonProperty("size_bytes") Integer sizeBytes,
    @JsonProperty("sha256") String sha256
) {

    public static ExternalFileReviewInput empty(){return new ExternalFileReviewInput(null,null,null,null,null,null);}
    public ExternalFileReviewInput withFilename(String value){return new ExternalFileReviewInput(value,contentType,mode,destinationId,sizeBytes,sha256);}
    public ExternalFileReviewInput withContentType(String value){return new ExternalFileReviewInput(filename,JsonField.of(value),mode,destinationId,sizeBytes,sha256);}
    public ExternalFileReviewInput clearContentType(){return new ExternalFileReviewInput(filename,JsonField.clear(),mode,destinationId,sizeBytes,sha256);}
    public ExternalFileReviewInput omitContentType(){return new ExternalFileReviewInput(filename,null,mode,destinationId,sizeBytes,sha256);}
    public ExternalFileReviewInput withMode(AddKnowledgeMode value){return new ExternalFileReviewInput(filename,contentType,value,destinationId,sizeBytes,sha256);}
    public ExternalFileReviewInput withDestinationId(String value){return new ExternalFileReviewInput(filename,contentType,mode,value,sizeBytes,sha256);}
    public ExternalFileReviewInput withSizeBytes(Integer value){return new ExternalFileReviewInput(filename,contentType,mode,destinationId,value,sha256);}
    public ExternalFileReviewInput withSha256(String value){return new ExternalFileReviewInput(filename,contentType,mode,destinationId,sizeBytes,value);}
}
