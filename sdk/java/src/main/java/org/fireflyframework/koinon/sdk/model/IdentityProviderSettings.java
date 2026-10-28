// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;


@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property="kind",visible=true)
@JsonSubTypes({@JsonSubTypes.Type(value=KeycloakSettings.class,name="keycloak"),@JsonSubTypes.Type(value=EntraSettings.class,name="entra"),@JsonSubTypes.Type(value=GoogleWorkspaceSettings.class,name="google_workspace")})
public sealed interface IdentityProviderSettings permits KeycloakSettings,EntraSettings,GoogleWorkspaceSettings {}
