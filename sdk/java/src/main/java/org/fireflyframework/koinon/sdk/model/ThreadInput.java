// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ThreadInput contract. */
public record ThreadInput(
    @JsonProperty("folder_id") JsonField<String> folderId,
    @JsonProperty("title") String title,
    @JsonProperty("scope") JsonField<KnowledgeScope> scope
) {

    public static ThreadInput empty(){return new ThreadInput(null,null,null);}
    public ThreadInput withFolderId(String value){return new ThreadInput(JsonField.of(value),title,scope);}
    public ThreadInput clearFolderId(){return new ThreadInput(JsonField.clear(),title,scope);}
    public ThreadInput omitFolderId(){return new ThreadInput(null,title,scope);}
    public ThreadInput withTitle(String value){return new ThreadInput(folderId,value,scope);}
    public ThreadInput withScope(KnowledgeScope value){return new ThreadInput(folderId,title,JsonField.of(value));}
    public ThreadInput clearScope(){return new ThreadInput(folderId,title,JsonField.clear());}
    public ThreadInput omitScope(){return new ThreadInput(folderId,title,null);}
}
