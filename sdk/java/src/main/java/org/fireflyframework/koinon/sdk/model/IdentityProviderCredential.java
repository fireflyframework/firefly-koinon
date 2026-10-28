// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;


@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property="kind",visible=true)
@JsonSubTypes({@JsonSubTypes.Type(value=KeycloakCredential.class,name="keycloak"),@JsonSubTypes.Type(value=EntraCredential.class,name="entra"),@JsonSubTypes.Type(value=GoogleCredential.class,name="google_workspace")})
public sealed interface IdentityProviderCredential permits KeycloakCredential,EntraCredential,GoogleCredential {}
