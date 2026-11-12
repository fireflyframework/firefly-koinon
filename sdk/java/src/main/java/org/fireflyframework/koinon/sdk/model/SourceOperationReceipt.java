// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;


@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property="kind",visible=true)
@JsonSubTypes({@JsonSubTypes.Type(value=SourcePolicyReceipt.class,name="policy"),@JsonSubTypes.Type(value=SourceControlReceipt.class,name="control")})
public sealed interface SourceOperationReceipt permits SourcePolicyReceipt,SourceControlReceipt {}
