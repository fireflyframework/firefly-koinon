// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceReplacementPreview contract. */
public record SourceReplacementPreview(
    @JsonProperty("object_id") String objectId,
    @JsonProperty("remote_version") String remoteVersion,
    @JsonProperty("content_sha256") String contentSha256,
    @JsonProperty("baseline_sha256") String baselineSha256,
    @JsonProperty("new_locator_set_sha256") String newLocatorSetSha256,
    @JsonProperty("parser_fingerprint") String parserFingerprint,
    @JsonProperty("previous_members") List<SourcePreviousMember> previousMembers,
    @JsonProperty("new_members") List<SourceDiscoveredMember> newMembers
) {
    public SourceReplacementPreview {
        previousMembers=previousMembers==null?null:List.copyOf(previousMembers);
        newMembers=newMembers==null?null:List.copyOf(newMembers);
    }

}
