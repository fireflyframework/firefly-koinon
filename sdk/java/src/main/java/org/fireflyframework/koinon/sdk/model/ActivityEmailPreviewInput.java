// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ActivityEmailPreviewInput contract. */
public record ActivityEmailPreviewInput(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("preferences") NotificationPreferencesInput preferences,
    @JsonProperty("window") ActivityWindow window
) {

    public static ActivityEmailPreviewInput empty(){return new ActivityEmailPreviewInput(null,null,null);}
    public ActivityEmailPreviewInput withTenantId(String value){return new ActivityEmailPreviewInput(value,preferences,window);}
    public ActivityEmailPreviewInput withPreferences(NotificationPreferencesInput value){return new ActivityEmailPreviewInput(tenantId,value,window);}
    public ActivityEmailPreviewInput withWindow(ActivityWindow value){return new ActivityEmailPreviewInput(tenantId,preferences,value);}
}
