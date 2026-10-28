// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;


@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property="action",visible=true)
@JsonSubTypes({@JsonSubTypes.Type(value=AddKnowledge.class,name="add"),@JsonSubTypes.Type(value=ReplaceDocument.class,name="replace_document"),@JsonSubTypes.Type(value=ReplaceTable.class,name="replace_table")})
public sealed interface AttachmentPromotionInput permits AddKnowledge,ReplaceDocument,ReplaceTable {}
