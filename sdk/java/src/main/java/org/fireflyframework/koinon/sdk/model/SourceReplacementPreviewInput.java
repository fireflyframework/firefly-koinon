// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceReplacementPreviewInput contract. */
public record SourceReplacementPreviewInput(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("remote_version") String remoteVersion
) {

    public static SourceReplacementPreviewInput empty(){return new SourceReplacementPreviewInput(null,null);}
    public SourceReplacementPreviewInput withExpectedRevision(Integer value){return new SourceReplacementPreviewInput(value,remoteVersion);}
    public SourceReplacementPreviewInput withRemoteVersion(String value){return new SourceReplacementPreviewInput(expectedRevision,value);}
}
