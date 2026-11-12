// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ReplacementResolutionInput contract. */
public record ReplacementResolutionInput(
    @JsonProperty("object_id") String objectId,
    @JsonProperty("remote_version") String remoteVersion,
    @JsonProperty("content_sha256") String contentSha256,
    @JsonProperty("baseline_sha256") String baselineSha256,
    @JsonProperty("new_locator_set_sha256") String newLocatorSetSha256,
    @JsonProperty("replacements") List<ReplacementMemberInput> replacements,
    @JsonProperty("removed_table_ids") List<String> removedTableIds
) {
    public ReplacementResolutionInput {
        replacements=replacements==null?null:List.copyOf(replacements);
        removedTableIds=removedTableIds==null?null:List.copyOf(removedTableIds);
    }

    public static ReplacementResolutionInput empty(){return new ReplacementResolutionInput(null,null,null,null,null,null,null);}
    public ReplacementResolutionInput withObjectId(String value){return new ReplacementResolutionInput(value,remoteVersion,contentSha256,baselineSha256,newLocatorSetSha256,replacements,removedTableIds);}
    public ReplacementResolutionInput withRemoteVersion(String value){return new ReplacementResolutionInput(objectId,value,contentSha256,baselineSha256,newLocatorSetSha256,replacements,removedTableIds);}
    public ReplacementResolutionInput withContentSha256(String value){return new ReplacementResolutionInput(objectId,remoteVersion,value,baselineSha256,newLocatorSetSha256,replacements,removedTableIds);}
    public ReplacementResolutionInput withBaselineSha256(String value){return new ReplacementResolutionInput(objectId,remoteVersion,contentSha256,value,newLocatorSetSha256,replacements,removedTableIds);}
    public ReplacementResolutionInput withNewLocatorSetSha256(String value){return new ReplacementResolutionInput(objectId,remoteVersion,contentSha256,baselineSha256,value,replacements,removedTableIds);}
    public ReplacementResolutionInput withReplacements(List<ReplacementMemberInput> value){return new ReplacementResolutionInput(objectId,remoteVersion,contentSha256,baselineSha256,newLocatorSetSha256,value,removedTableIds);}
    public ReplacementResolutionInput withRemovedTableIds(List<String> value){return new ReplacementResolutionInput(objectId,remoteVersion,contentSha256,baselineSha256,newLocatorSetSha256,replacements,value);}
}
