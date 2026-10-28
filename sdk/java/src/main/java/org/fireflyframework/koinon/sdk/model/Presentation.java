// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical Presentation contract. */
public record Presentation(
    @JsonProperty("locale") String locale,
    @JsonProperty("time_zone") String timeZone,
    @JsonProperty("response_language") String responseLanguage
) {

    public static Presentation empty(){return new Presentation(null,null,null);}
    public Presentation withLocale(String value){return new Presentation(value,timeZone,responseLanguage);}
    public Presentation withTimeZone(String value){return new Presentation(locale,value,responseLanguage);}
    public Presentation withResponseLanguage(String value){return new Presentation(locale,timeZone,value);}
}
