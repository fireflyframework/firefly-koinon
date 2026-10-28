// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ThreadPatch contract. */
public record ThreadPatch(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("title") JsonField<String> title,
    @JsonProperty("folder_id") JsonField<String> folderId,
    @JsonProperty("archived") JsonField<Boolean> archived
) {

    public static ThreadPatch empty(){return new ThreadPatch(null,null,null,null);}
    public ThreadPatch withExpectedRevision(Long value){return new ThreadPatch(value,title,folderId,archived);}
    public ThreadPatch withTitle(String value){return new ThreadPatch(expectedRevision,JsonField.of(value),folderId,archived);}
    public ThreadPatch clearTitle(){return new ThreadPatch(expectedRevision,JsonField.clear(),folderId,archived);}
    public ThreadPatch omitTitle(){return new ThreadPatch(expectedRevision,null,folderId,archived);}
    public ThreadPatch withFolderId(String value){return new ThreadPatch(expectedRevision,title,JsonField.of(value),archived);}
    public ThreadPatch clearFolderId(){return new ThreadPatch(expectedRevision,title,JsonField.clear(),archived);}
    public ThreadPatch omitFolderId(){return new ThreadPatch(expectedRevision,title,null,archived);}
    public ThreadPatch withArchived(Boolean value){return new ThreadPatch(expectedRevision,title,folderId,JsonField.of(value));}
    public ThreadPatch clearArchived(){return new ThreadPatch(expectedRevision,title,folderId,JsonField.clear());}
    public ThreadPatch omitArchived(){return new ThreadPatch(expectedRevision,title,folderId,null);}
}
