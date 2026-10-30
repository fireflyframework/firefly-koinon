// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum McpReadReceiptReason {
    INCOMPLETE_OR_UNSUPPORTED_SOURCE_MANIFEST("incomplete_or_unsupported_source_manifest"),
    SOURCE_MANIFEST_LIMIT_OR_MISSING_REVISION("source_manifest_limit_or_missing_revision"),
    RECEIPT_BYTE_LIMIT("receipt_byte_limit"),
    ACTIVE_RECEIPT_LIMIT("active_receipt_limit"),
    SOURCE_REUSE_SCOPE_REQUIRED("source_reuse_scope_required"),
    CAPTURE_UNAVAILABLE("capture_unavailable"),
    TRANSITIVE_LINEAGE_UNQUALIFIED("transitive_lineage_unqualified"),
    CATALOG_IS_NOT_SOURCE_EVIDENCE("catalog_is_not_source_evidence");
    private final String value;
    McpReadReceiptReason(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static McpReadReceiptReason from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown McpReadReceiptReason value: "+value);}
}
