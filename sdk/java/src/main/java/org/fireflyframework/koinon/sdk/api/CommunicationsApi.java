// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class CommunicationsApi {
private final Transport transport; private final String prefix;
public CommunicationsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public RecipientProviderPage recipientProviders(RecipientProviderFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/communications/recipient-providers",null,options,transport.type(RecipientProviderPage.class));}
public RecipientProviderPage recipientProviders(RecipientProviderFilter filter){return recipientProviders(filter,RequestOptions.defaults());}
public RecipientProviderPage recipientProviders(){return recipientProviders(RecipientProviderFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<RecipientProviderPage> recipientProvidersAsync(RecipientProviderFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/communications/recipient-providers",null,options,transport.type(RecipientProviderPage.class));}
public CompletableFuture<RecipientProviderPage> recipientProvidersAsync(RecipientProviderFilter filter){return recipientProvidersAsync(filter,RequestOptions.defaults());}
public CompletableFuture<RecipientProviderPage> recipientProvidersAsync(){return recipientProvidersAsync(RecipientProviderFilter.empty(),RequestOptions.defaults());}
public DirectoryRecipientPage recipients(RecipientFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/communications/recipients",null,options,transport.type(DirectoryRecipientPage.class));}
public DirectoryRecipientPage recipients(RecipientFilter filter){return recipients(filter,RequestOptions.defaults());}
public DirectoryRecipientPage recipients(){return recipients(RecipientFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<DirectoryRecipientPage> recipientsAsync(RecipientFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/communications/recipients",null,options,transport.type(DirectoryRecipientPage.class));}
public CompletableFuture<DirectoryRecipientPage> recipientsAsync(RecipientFilter filter){return recipientsAsync(filter,RequestOptions.defaults());}
public CompletableFuture<DirectoryRecipientPage> recipientsAsync(){return recipientsAsync(RecipientFilter.empty(),RequestOptions.defaults());}
public EmailPreview previewInvitation(EmailInvitationInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/invitations/email/preview",input,options,transport.type(EmailPreview.class));}
public EmailPreview previewInvitation(EmailInvitationInput input){return previewInvitation(input,RequestOptions.defaults());}
public CompletableFuture<EmailPreview> previewInvitationAsync(EmailInvitationInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/invitations/email/preview",input,options,transport.type(EmailPreview.class));}
public CompletableFuture<EmailPreview> previewInvitationAsync(EmailInvitationInput input){return previewInvitationAsync(input,RequestOptions.defaults());}
public EmailInvitation createInvitation(EmailInvitationInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/invitations/email",input,options,transport.type(EmailInvitation.class));}
public EmailInvitation createInvitation(EmailInvitationInput input,String idempotencyKey){return createInvitation(input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<EmailInvitation> createInvitationAsync(EmailInvitationInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/invitations/email",input,options,transport.type(EmailInvitation.class));}
public CompletableFuture<EmailInvitation> createInvitationAsync(EmailInvitationInput input,String idempotencyKey){return createInvitationAsync(input,idempotencyKey,RequestOptions.defaults());}
public EmailInvitationPage invitations(EmailInvitationFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/invitations/email",null,options,transport.type(EmailInvitationPage.class));}
public EmailInvitationPage invitations(EmailInvitationFilter filter){return invitations(filter,RequestOptions.defaults());}
public EmailInvitationPage invitations(){return invitations(EmailInvitationFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<EmailInvitationPage> invitationsAsync(EmailInvitationFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/invitations/email",null,options,transport.type(EmailInvitationPage.class));}
public CompletableFuture<EmailInvitationPage> invitationsAsync(EmailInvitationFilter filter){return invitationsAsync(filter,RequestOptions.defaults());}
public CompletableFuture<EmailInvitationPage> invitationsAsync(){return invitationsAsync(EmailInvitationFilter.empty(),RequestOptions.defaults());}
public Void revokeInvitation(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/invitations/email/"+Transport.id(invitationId),null,options,transport.type(Void.class));}
public Void revokeInvitation(String invitationId){return revokeInvitation(invitationId,RequestOptions.defaults());}
public CompletableFuture<Void> revokeInvitationAsync(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/invitations/email/"+Transport.id(invitationId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> revokeInvitationAsync(String invitationId){return revokeInvitationAsync(invitationId,RequestOptions.defaults());}
public EmailInvitation resendInvitation(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/invitations/email/"+Transport.id(invitationId)+"/resend",null,options,transport.type(EmailInvitation.class));}
public EmailInvitation resendInvitation(String invitationId){return resendInvitation(invitationId,RequestOptions.defaults());}
public CompletableFuture<EmailInvitation> resendInvitationAsync(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/invitations/email/"+Transport.id(invitationId)+"/resend",null,options,transport.type(EmailInvitation.class));}
public CompletableFuture<EmailInvitation> resendInvitationAsync(String invitationId){return resendInvitationAsync(invitationId,RequestOptions.defaults());}
public CommunicationCapabilities capabilities(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/communications/capabilities",null,options,transport.type(CommunicationCapabilities.class));}
public CommunicationCapabilities capabilities(){return capabilities(RequestOptions.defaults());}
public CompletableFuture<CommunicationCapabilities> capabilitiesAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/communications/capabilities",null,options,transport.type(CommunicationCapabilities.class));}
public CompletableFuture<CommunicationCapabilities> capabilitiesAsync(){return capabilitiesAsync(RequestOptions.defaults());}
public CommunicationPolicy policy(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/communications/policy",null,options,transport.type(CommunicationPolicy.class));}
public CommunicationPolicy policy(){return policy(RequestOptions.defaults());}
public CompletableFuture<CommunicationPolicy> policyAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/communications/policy",null,options,transport.type(CommunicationPolicy.class));}
public CompletableFuture<CommunicationPolicy> policyAsync(){return policyAsync(RequestOptions.defaults());}
public CommunicationPolicy updatePolicy(CommunicationPolicyInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/communications/policy",input,options,transport.type(CommunicationPolicy.class));}
public CommunicationPolicy updatePolicy(CommunicationPolicyInput input){return updatePolicy(input,RequestOptions.defaults());}
public CompletableFuture<CommunicationPolicy> updatePolicyAsync(CommunicationPolicyInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/communications/policy",input,options,transport.type(CommunicationPolicy.class));}
public CompletableFuture<CommunicationPolicy> updatePolicyAsync(CommunicationPolicyInput input){return updatePolicyAsync(input,RequestOptions.defaults());}
public DeliveryPage deliveries(CommunicationDeliveryFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/communications/deliveries",null,options,transport.type(DeliveryPage.class));}
public DeliveryPage deliveries(CommunicationDeliveryFilter filter){return deliveries(filter,RequestOptions.defaults());}
public DeliveryPage deliveries(){return deliveries(CommunicationDeliveryFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<DeliveryPage> deliveriesAsync(CommunicationDeliveryFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/communications/deliveries",null,options,transport.type(DeliveryPage.class));}
public CompletableFuture<DeliveryPage> deliveriesAsync(CommunicationDeliveryFilter filter){return deliveriesAsync(filter,RequestOptions.defaults());}
public CompletableFuture<DeliveryPage> deliveriesAsync(){return deliveriesAsync(CommunicationDeliveryFilter.empty(),RequestOptions.defaults());}
public DeliveryRecord delivery(String deliveryId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/communications/deliveries/"+Transport.id(deliveryId),null,options,transport.type(DeliveryRecord.class));}
public DeliveryRecord delivery(String deliveryId){return delivery(deliveryId,RequestOptions.defaults());}
public CompletableFuture<DeliveryRecord> deliveryAsync(String deliveryId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/communications/deliveries/"+Transport.id(deliveryId),null,options,transport.type(DeliveryRecord.class));}
public CompletableFuture<DeliveryRecord> deliveryAsync(String deliveryId){return deliveryAsync(deliveryId,RequestOptions.defaults());}
public DeliveryRecord retryDelivery(String deliveryId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/communications/deliveries/"+Transport.id(deliveryId)+"/retry",null,options,transport.type(DeliveryRecord.class));}
public DeliveryRecord retryDelivery(String deliveryId){return retryDelivery(deliveryId,RequestOptions.defaults());}
public CompletableFuture<DeliveryRecord> retryDeliveryAsync(String deliveryId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/communications/deliveries/"+Transport.id(deliveryId)+"/retry",null,options,transport.type(DeliveryRecord.class));}
public CompletableFuture<DeliveryRecord> retryDeliveryAsync(String deliveryId){return retryDeliveryAsync(deliveryId,RequestOptions.defaults());}
}
