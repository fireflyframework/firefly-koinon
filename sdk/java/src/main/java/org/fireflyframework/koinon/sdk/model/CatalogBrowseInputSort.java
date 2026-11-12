// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum CatalogBrowseInputSort {
    NAME("name"),
    KIND("kind"),
    CREATED_AT("created_at"),
    UPDATED_AT("updated_at");
    private final String value;
    CatalogBrowseInputSort(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static CatalogBrowseInputSort from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown CatalogBrowseInputSort value: "+value);}
}
