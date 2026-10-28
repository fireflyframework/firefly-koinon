// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;


@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property="kind",visible=true)
@JsonSubTypes({@JsonSubTypes.Type(value=ConversationExportInput.class,name="conversation"),@JsonSubTypes.Type(value=QueryResultExportInput.class,name="query_result")})
public sealed interface ExportReviewRequest permits ConversationExportInput,QueryResultExportInput {}
