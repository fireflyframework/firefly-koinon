// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum KnowledgeModeTargetViewAction {
    REPROCESS_DOCUMENT("reprocess_document"),
    INSPECT_DOCUMENT_JOB("inspect_document_job"),
    KEEP_RAG("keep_rag"),
    INSPECT_SOURCE_INTEGRITY("inspect_source_integrity"),
    INSPECT_SOURCE_LIMITS("inspect_source_limits"),
    RESTART_PREPARATION("restart_preparation"),
    RETRY_PREPARATION("retry_preparation"),
    CONFIGURE_MODELS("configure_models"),
    INSPECT_PREPARATION("inspect_preparation"),
    INSPECT_INDEX_JOB("inspect_index_job"),
    RECONCILE_INDEX("reconcile_index");
    private final String value;
    KnowledgeModeTargetViewAction(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static KnowledgeModeTargetViewAction from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown KnowledgeModeTargetViewAction value: "+value);}
}
