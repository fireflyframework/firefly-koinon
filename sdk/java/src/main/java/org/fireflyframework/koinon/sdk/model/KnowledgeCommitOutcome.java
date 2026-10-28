// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;


@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property="status",visible=true)
@JsonSubTypes({@JsonSubTypes.Type(value=CommittedKnowledge.class,name="committed"),@JsonSubTypes.Type(value=PendingKnowledgeCommit.class,name="pending")})
public sealed interface KnowledgeCommitOutcome permits CommittedKnowledge,PendingKnowledgeCommit {}
