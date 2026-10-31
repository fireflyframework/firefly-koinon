// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import java.net.URI;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.Objects;
import java.util.function.Supplier;
import org.fireflyframework.koinon.sdk.api.*;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.internal.Transport;

/** A headless API client; credentials are obtained again for every request. */
public final class KoinonClient implements AutoCloseable {
  private final Transport transport;

  private KoinonClient(Builder builder) {
    var http =
        builder.http != null
            ? builder.http
            : HttpClient.newBuilder()
                .connectTimeout(builder.connectTimeout)
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
    transport =
        new Transport(builder.base, http, builder.http == null, builder.bearer, new JsonCodec());
  }

  public static Builder builder(URI base) {
    return new Builder(base);
  }

  public McpApi mcp() { return new McpApi(transport); }

  public McpOAuthClientsApi mcpOAuthClients(String tenant) { return new McpOAuthClientsApi(transport, tenant); }

  public ExternalReviewsApi externalReviews(String tenant) { return new ExternalReviewsApi(transport, tenant); }

  public ExternalFileReviewsApi externalFileReviews(String tenant) { return new ExternalFileReviewsApi(transport, tenant); }

  public PlatformApi platform() {
    return new PlatformApi(transport);
  }

  public ProfileApi profile() {
    return new ProfileApi(transport);
  }

  public OrganizationPeopleApi organizationPeople(String tenant) {
    return new OrganizationPeopleApi(transport, tenant);
  }

  public FileBatchesApi fileBatches(String tenant) { return new FileBatchesApi(transport, tenant); }
  public QueryBatchesApi queryBatches(String tenant) { return new QueryBatchesApi(transport, tenant); }

  public CorporateProfilesApi corporateProfiles(String tenant) {
    return new CorporateProfilesApi(transport, tenant);
  }

  public TokensApi tokens() {
    return new TokensApi(transport);
  }

  public AuthorizedApplicationsApi authorizedApplications() {
    return new AuthorizedApplicationsApi(transport);
  }

  public CatalogApi catalog(String tenant) {
    return new CatalogApi(transport, tenant);
  }

  public SourcesApi sources(String tenant) {
    return new SourcesApi(transport, tenant);
  }

  public DatasetsApi datasets(String tenant) {
    return new DatasetsApi(transport, tenant);
  }

  public DocumentsApi documents(String tenant) {
    return new DocumentsApi(transport, tenant);
  }

  public JobsApi jobs(String tenant) {
    return new JobsApi(transport, tenant);
  }

  public MembersApi members(String tenant) {
    return new MembersApi(transport, tenant);
  }

  public InvitationsApi invitations(String tenant) {
    return new InvitationsApi(transport, tenant);
  }

  public InvitationAccessApi invitationAccess() {
    return new InvitationAccessApi(transport);
  }

  public PeopleApi people(String tenant) {
    return new PeopleApi(transport, tenant);
  }

  public AuditApi audit(String tenant) {
    return new AuditApi(transport, tenant);
  }

  public ConfigurationApi configuration(String tenant) {
    return new ConfigurationApi(transport, tenant);
  }

  public ProvidersApi providers(String tenant) {
    return new ProvidersApi(transport, tenant);
  }

  public OrganizationChatApi organizationChat(String tenant) {
    return new OrganizationChatApi(transport, tenant);
  }

  public BrandingDefaultsApi brandingDefaults() {
    return new BrandingDefaultsApi(transport);
  }

  public OrganizationBrandingApi organizationBranding(String tenant) {
    return new OrganizationBrandingApi(transport, tenant);
  }

  public BrandingDefaultsApi branding() {
    return brandingDefaults();
  }

  public OrganizationBrandingApi branding(String tenant) {
    return organizationBranding(tenant);
  }

  public OrganizationKnowledgeApi organizationKnowledge(String tenant) {
    return new OrganizationKnowledgeApi(transport, tenant);
  }

  public AgentsApi agents(String tenant) {
    return new AgentsApi(transport, tenant);
  }

  public ChatApi chat(String tenant) {
    return new ChatApi(transport, tenant);
  }

  public KnowledgeApi knowledge(String tenant) {
    return new KnowledgeApi(transport, tenant);
  }

  public KnowledgeConnectionsApi knowledgeConnections(String tenant) {
    return new KnowledgeConnectionsApi(transport, tenant);
  }

  public KnowledgeIntentsApi knowledgeIntents(String tenant) {
    return new KnowledgeIntentsApi(transport, tenant);
  }

  public KnowledgeItemsApi knowledgeItems(String tenant) {
    return new KnowledgeItemsApi(transport, tenant);
  }

  public ChatAttachmentsApi chatAttachments(String tenant) {
    return new ChatAttachmentsApi(transport, tenant);
  }

  public ChatFoldersApi chatFolders(String tenant) {
    return new ChatFoldersApi(transport, tenant);
  }

  public KnowledgeIndexesApi knowledgeIndexes(String tenant) {
    return new KnowledgeIndexesApi(transport, tenant);
  }

  public IdentityApi identity(String tenant) {
    return new IdentityApi(transport, tenant);
  }

  public ExportsApi exports(String tenant) { return new ExportsApi(transport, tenant); }
  public SharesApi shares(String tenant) { return new SharesApi(transport, tenant); }
  public ChatProposalsApi chatProposals(String tenant) { return new ChatProposalsApi(transport, tenant); }

  public EvidenceApi evidence(String tenant) { return new EvidenceApi(transport, tenant); }

  public StructuredGlossaryApi structuredGlossary(String tenant, String workspace) { return new StructuredGlossaryApi(transport, tenant, workspace, false); }
  public StructuredGlossaryApi structuredAgentGlossary(String tenant, String workspace) { return new StructuredGlossaryApi(transport, tenant, workspace, true); }

  @Override
  public void close() {
    transport.close();
  }

  public static final class Builder {
    private final URI base;
    private Supplier<String> bearer;
    private HttpClient http;
    private Duration connectTimeout = Duration.ofSeconds(10);

    private Builder(URI base) {
      Transport.validate(base);
      this.base = base;
    }

    public Builder bearerToken(Supplier<String> value) {
      bearer = Objects.requireNonNull(value);
      return this;
    }

    public Builder httpClient(HttpClient value) {
      http = Objects.requireNonNull(value);
      return this;
    }

    public Builder connectTimeout(Duration value) {
      if (value == null || value.isNegative() || value.isZero())
        throw new IllegalArgumentException("Connect timeout must be positive");
      connectTimeout = value;
      return this;
    }

    public KoinonClient build() {
      return new KoinonClient(this);
    }
  }
}
