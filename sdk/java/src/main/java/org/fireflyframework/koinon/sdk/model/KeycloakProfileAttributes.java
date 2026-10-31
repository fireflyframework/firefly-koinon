// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KeycloakProfileAttributes contract. */
public record KeycloakProfileAttributes(
    @JsonProperty("display_name") JsonField<String> displayName,
    @JsonProperty("job_title") JsonField<String> jobTitle,
    @JsonProperty("department") JsonField<String> department,
    @JsonProperty("manager") JsonField<String> manager,
    @JsonProperty("picture") JsonField<String> picture
) {

    public static KeycloakProfileAttributes empty(){return new KeycloakProfileAttributes(null,null,null,null,null);}
    public KeycloakProfileAttributes withDisplayName(String value){return new KeycloakProfileAttributes(JsonField.of(value),jobTitle,department,manager,picture);}
    public KeycloakProfileAttributes clearDisplayName(){return new KeycloakProfileAttributes(JsonField.clear(),jobTitle,department,manager,picture);}
    public KeycloakProfileAttributes omitDisplayName(){return new KeycloakProfileAttributes(null,jobTitle,department,manager,picture);}
    public KeycloakProfileAttributes withJobTitle(String value){return new KeycloakProfileAttributes(displayName,JsonField.of(value),department,manager,picture);}
    public KeycloakProfileAttributes clearJobTitle(){return new KeycloakProfileAttributes(displayName,JsonField.clear(),department,manager,picture);}
    public KeycloakProfileAttributes omitJobTitle(){return new KeycloakProfileAttributes(displayName,null,department,manager,picture);}
    public KeycloakProfileAttributes withDepartment(String value){return new KeycloakProfileAttributes(displayName,jobTitle,JsonField.of(value),manager,picture);}
    public KeycloakProfileAttributes clearDepartment(){return new KeycloakProfileAttributes(displayName,jobTitle,JsonField.clear(),manager,picture);}
    public KeycloakProfileAttributes omitDepartment(){return new KeycloakProfileAttributes(displayName,jobTitle,null,manager,picture);}
    public KeycloakProfileAttributes withManager(String value){return new KeycloakProfileAttributes(displayName,jobTitle,department,JsonField.of(value),picture);}
    public KeycloakProfileAttributes clearManager(){return new KeycloakProfileAttributes(displayName,jobTitle,department,JsonField.clear(),picture);}
    public KeycloakProfileAttributes omitManager(){return new KeycloakProfileAttributes(displayName,jobTitle,department,null,picture);}
    public KeycloakProfileAttributes withPicture(String value){return new KeycloakProfileAttributes(displayName,jobTitle,department,manager,JsonField.of(value));}
    public KeycloakProfileAttributes clearPicture(){return new KeycloakProfileAttributes(displayName,jobTitle,department,manager,JsonField.clear());}
    public KeycloakProfileAttributes omitPicture(){return new KeycloakProfileAttributes(displayName,jobTitle,department,manager,null);}
}
