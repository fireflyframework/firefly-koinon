// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class NotificationsApi {
private final Transport transport; private final String prefix;
public NotificationsApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public OwnNotificationPage list(NotificationFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/notifications",null,options,transport.type(OwnNotificationPage.class));}
public OwnNotificationPage list(NotificationFilter filter){return list(filter,RequestOptions.defaults());}
public OwnNotificationPage list(){return list(NotificationFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OwnNotificationPage> listAsync(NotificationFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/notifications",null,options,transport.type(OwnNotificationPage.class));}
public CompletableFuture<OwnNotificationPage> listAsync(NotificationFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<OwnNotificationPage> listAsync(){return listAsync(NotificationFilter.empty(),RequestOptions.defaults());}
public NotificationUnreadCount unreadCount(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/notifications/unread-count",null,options,transport.type(NotificationUnreadCount.class));}
public NotificationUnreadCount unreadCount(){return unreadCount(RequestOptions.defaults());}
public CompletableFuture<NotificationUnreadCount> unreadCountAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/notifications/unread-count",null,options,transport.type(NotificationUnreadCount.class));}
public CompletableFuture<NotificationUnreadCount> unreadCountAsync(){return unreadCountAsync(RequestOptions.defaults());}
public OwnNotification markRead(String notificationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/notifications/"+Transport.id(notificationId)+"/read",null,options,transport.type(OwnNotification.class));}
public OwnNotification markRead(String notificationId){return markRead(notificationId,RequestOptions.defaults());}
public CompletableFuture<OwnNotification> markReadAsync(String notificationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/notifications/"+Transport.id(notificationId)+"/read",null,options,transport.type(OwnNotification.class));}
public CompletableFuture<OwnNotification> markReadAsync(String notificationId){return markReadAsync(notificationId,RequestOptions.defaults());}
public NotificationPreferences preferences(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/notifications/preferences",null,options,transport.type(NotificationPreferences.class));}
public NotificationPreferences preferences(){return preferences(RequestOptions.defaults());}
public CompletableFuture<NotificationPreferences> preferencesAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/notifications/preferences",null,options,transport.type(NotificationPreferences.class));}
public CompletableFuture<NotificationPreferences> preferencesAsync(){return preferencesAsync(RequestOptions.defaults());}
public NotificationPreferences updatePreferences(NotificationPreferencesInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/notifications/preferences",input,options,transport.type(NotificationPreferences.class));}
public NotificationPreferences updatePreferences(NotificationPreferencesInput input){return updatePreferences(input,RequestOptions.defaults());}
public CompletableFuture<NotificationPreferences> updatePreferencesAsync(NotificationPreferencesInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/notifications/preferences",input,options,transport.type(NotificationPreferences.class));}
public CompletableFuture<NotificationPreferences> updatePreferencesAsync(NotificationPreferencesInput input){return updatePreferencesAsync(input,RequestOptions.defaults());}
public DigestSchedulePreview previewSchedule(NotificationPreferencesInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/notifications/preferences/preview",input,options,transport.type(DigestSchedulePreview.class));}
public DigestSchedulePreview previewSchedule(NotificationPreferencesInput input){return previewSchedule(input,RequestOptions.defaults());}
public CompletableFuture<DigestSchedulePreview> previewScheduleAsync(NotificationPreferencesInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/notifications/preferences/preview",input,options,transport.type(DigestSchedulePreview.class));}
public CompletableFuture<DigestSchedulePreview> previewScheduleAsync(NotificationPreferencesInput input){return previewScheduleAsync(input,RequestOptions.defaults());}
public EmailPreview previewEmail(ActivityEmailPreviewInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/notifications/preferences/email-preview",input,options,transport.type(EmailPreview.class));}
public EmailPreview previewEmail(ActivityEmailPreviewInput input){return previewEmail(input,RequestOptions.defaults());}
public CompletableFuture<EmailPreview> previewEmailAsync(ActivityEmailPreviewInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/notifications/preferences/email-preview",input,options,transport.type(EmailPreview.class));}
public CompletableFuture<EmailPreview> previewEmailAsync(ActivityEmailPreviewInput input){return previewEmailAsync(input,RequestOptions.defaults());}
}
