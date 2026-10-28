// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical GoogleCredential contract. */
public record GoogleCredential(
    @JsonProperty("kind") GoogleCredentialKind kind,
    @JsonProperty("secret") JsonField<String> secret,
    @JsonProperty("service_account_email") JsonField<String> serviceAccountEmail,
    @JsonProperty("private_key") JsonField<String> privateKey,
    @JsonProperty("private_key_id") JsonField<String> privateKeyId,
    @JsonProperty("delegated_admin") JsonField<String> delegatedAdmin
) implements IdentityProviderCredential {

    public static GoogleCredential empty(){return new GoogleCredential(null,null,null,null,null,null);}
    public GoogleCredential withKind(GoogleCredentialKind value){return new GoogleCredential(value,secret,serviceAccountEmail,privateKey,privateKeyId,delegatedAdmin);}
    public GoogleCredential withSecret(String value){return new GoogleCredential(kind,JsonField.of(value),serviceAccountEmail,privateKey,privateKeyId,delegatedAdmin);}
    public GoogleCredential clearSecret(){return new GoogleCredential(kind,JsonField.clear(),serviceAccountEmail,privateKey,privateKeyId,delegatedAdmin);}
    public GoogleCredential omitSecret(){return new GoogleCredential(kind,null,serviceAccountEmail,privateKey,privateKeyId,delegatedAdmin);}
    public GoogleCredential withServiceAccountEmail(String value){return new GoogleCredential(kind,secret,JsonField.of(value),privateKey,privateKeyId,delegatedAdmin);}
    public GoogleCredential clearServiceAccountEmail(){return new GoogleCredential(kind,secret,JsonField.clear(),privateKey,privateKeyId,delegatedAdmin);}
    public GoogleCredential omitServiceAccountEmail(){return new GoogleCredential(kind,secret,null,privateKey,privateKeyId,delegatedAdmin);}
    public GoogleCredential withPrivateKey(String value){return new GoogleCredential(kind,secret,serviceAccountEmail,JsonField.of(value),privateKeyId,delegatedAdmin);}
    public GoogleCredential clearPrivateKey(){return new GoogleCredential(kind,secret,serviceAccountEmail,JsonField.clear(),privateKeyId,delegatedAdmin);}
    public GoogleCredential omitPrivateKey(){return new GoogleCredential(kind,secret,serviceAccountEmail,null,privateKeyId,delegatedAdmin);}
    public GoogleCredential withPrivateKeyId(String value){return new GoogleCredential(kind,secret,serviceAccountEmail,privateKey,JsonField.of(value),delegatedAdmin);}
    public GoogleCredential clearPrivateKeyId(){return new GoogleCredential(kind,secret,serviceAccountEmail,privateKey,JsonField.clear(),delegatedAdmin);}
    public GoogleCredential omitPrivateKeyId(){return new GoogleCredential(kind,secret,serviceAccountEmail,privateKey,null,delegatedAdmin);}
    public GoogleCredential withDelegatedAdmin(String value){return new GoogleCredential(kind,secret,serviceAccountEmail,privateKey,privateKeyId,JsonField.of(value));}
    public GoogleCredential clearDelegatedAdmin(){return new GoogleCredential(kind,secret,serviceAccountEmail,privateKey,privateKeyId,JsonField.clear());}
    public GoogleCredential omitDelegatedAdmin(){return new GoogleCredential(kind,secret,serviceAccountEmail,privateKey,privateKeyId,null);}
}
