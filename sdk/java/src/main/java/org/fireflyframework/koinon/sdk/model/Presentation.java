// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical Presentation contract. */
public record Presentation(
    @JsonProperty("locale") String locale,
    @JsonProperty("time_zone") String timeZone,
    @JsonProperty("response_language") String responseLanguage,
    @JsonProperty("effective_language") PresentationEffectiveLanguage effectiveLanguage
) {
    public Presentation(String locale, String timeZone, String responseLanguage){this(locale,timeZone,responseLanguage,null);}

    public static Presentation empty(){return new Presentation(null,null,null,null);}
    public Presentation withLocale(String value){return new Presentation(value,timeZone,responseLanguage,effectiveLanguage);}
    public Presentation withTimeZone(String value){return new Presentation(locale,value,responseLanguage,effectiveLanguage);}
    public Presentation withResponseLanguage(String value){return new Presentation(locale,timeZone,value,effectiveLanguage);}
    public Presentation withEffectiveLanguage(PresentationEffectiveLanguage value){return new Presentation(locale,timeZone,responseLanguage,value);}
}
