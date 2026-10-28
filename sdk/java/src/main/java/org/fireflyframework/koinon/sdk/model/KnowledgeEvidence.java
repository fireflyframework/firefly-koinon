// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;


@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property="kind",visible=true)
@JsonSubTypes({@JsonSubTypes.Type(value=UserStatementEvidence.class,name="user_statement"),@JsonSubTypes.Type(value=DocumentEvidence.class,name="document_passage"),@JsonSubTypes.Type(value=StructuredEvidence.class,name="structured_snapshot")})
public sealed interface KnowledgeEvidence permits UserStatementEvidence,DocumentEvidence,StructuredEvidence {}
