// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ReplaceDocument contract. */
public record ReplaceDocument(
    @JsonProperty("expected_source_version_id") JsonField<String> expectedSourceVersionId,
    @JsonProperty("expected_extraction_id") JsonField<String> expectedExtractionId,
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("action") ReplaceDocumentAction action,
    @JsonProperty("document_id") String documentId,
    @JsonProperty("expected_sha256") String expectedSha256,
    @JsonProperty("acknowledge_chunk_invalidation") Boolean acknowledgeChunkInvalidation
) implements AttachmentPromotionInput {

    public static ReplaceDocument empty(){return new ReplaceDocument(null,null,null,null,null,null,null);}
    public ReplaceDocument withExpectedSourceVersionId(String value){return new ReplaceDocument(JsonField.of(value),expectedExtractionId,expectedRevision,action,documentId,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument clearExpectedSourceVersionId(){return new ReplaceDocument(JsonField.clear(),expectedExtractionId,expectedRevision,action,documentId,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument omitExpectedSourceVersionId(){return new ReplaceDocument(null,expectedExtractionId,expectedRevision,action,documentId,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument withExpectedExtractionId(String value){return new ReplaceDocument(expectedSourceVersionId,JsonField.of(value),expectedRevision,action,documentId,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument clearExpectedExtractionId(){return new ReplaceDocument(expectedSourceVersionId,JsonField.clear(),expectedRevision,action,documentId,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument omitExpectedExtractionId(){return new ReplaceDocument(expectedSourceVersionId,null,expectedRevision,action,documentId,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument withExpectedRevision(Long value){return new ReplaceDocument(expectedSourceVersionId,expectedExtractionId,value,action,documentId,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument withAction(ReplaceDocumentAction value){return new ReplaceDocument(expectedSourceVersionId,expectedExtractionId,expectedRevision,value,documentId,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument withDocumentId(String value){return new ReplaceDocument(expectedSourceVersionId,expectedExtractionId,expectedRevision,action,value,expectedSha256,acknowledgeChunkInvalidation);}
    public ReplaceDocument withExpectedSha256(String value){return new ReplaceDocument(expectedSourceVersionId,expectedExtractionId,expectedRevision,action,documentId,value,acknowledgeChunkInvalidation);}
    public ReplaceDocument withAcknowledgeChunkInvalidation(Boolean value){return new ReplaceDocument(expectedSourceVersionId,expectedExtractionId,expectedRevision,action,documentId,expectedSha256,value);}
}
