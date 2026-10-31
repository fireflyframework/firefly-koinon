<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Corporate profile synchronization

Corporate profile synchronization maintains organization-specific names, photos and positions from a configured Keycloak, Microsoft Entra ID or Google Workspace connection. It does not import every directory user, grant membership or derive permissions from a job title. A verified sign-in establishes the relationship to the existing koinon user before the directory can supply presentation data.

Personal display names, uploaded photos, language, time zone and response preferences remain in the global personal profile. Each organization keeps a separate corporate snapshot and presentation preference. Existing personal values are preserved, including older photos whose original source was never recorded.

## Prepare the corporate connection

Configure sign-in and the corporate directory connection with an organization administrator's ordinary verified identity. Personal API tokens cannot administer corporate providers, discover their groups or change group/profile mappings. The connection's directory credential is stored on the server and is separate from a user's koinon API token or an authorized MCP application's token.

Select the exact issuer, tenant or hosted domain belonging to the organization. Supply the directory credential through the existing corporate access configuration, validate the connection and activate it only after reviewing the selected source. Group-to-role mappings remain a separate access policy. Read [identity and appearance](../operations/identity-appearance.md) and [API permissions](api-permissions.md) before delegating administration.

| Provider | Directory configuration | Presentation prerequisites |
| --- | --- | --- |
| Keycloak | Exact realm issuer; login client; optional separate directory client and secret. | User-view authority for that realm and explicitly configured attributes for title, department, manager and optional picture. |
| Microsoft Entra ID | Exact tenant UUID; client ID; optional separate directory client and secret. | Administrator-consented Microsoft Graph application permissions for the fields being read. |
| Google Workspace | Approved hosted domains and customer binding; service-account identity, key and delegated administrator. | Enabled Admin SDK and approved domain-wide delegation for the requested directory scopes. |

Credentials and consent are not established by saving the form. Validate with an account and directory records owned by the deployment, then inspect field observations. Never paste provider secrets, private keys or raw identity tokens into chat or an issue report.

### Keycloak

The directory reads the verified user's stable ID from the configured realm. Standard first and last names supply the display name unless an explicit display-name attribute is configured. Title, department and manager require configured single-valued attributes. A manager attribute must identify an existing person through that same provider's stable external ID; names and email addresses are not identity keys.

Keep authoritative corporate attributes administrator-managed in the identity provider. If members can edit those attributes themselves, the directory observation reflects that editable source; it is not independent verification of their position. Neither presentation source grants koinon access.

Keycloak's documented user representation supplies attributes but no standard binary profile-photo field. koinon therefore supports a picture only through an explicitly selected attribute containing a permitted HTTPS URL. The installation operator must allow its exact origin and path prefix before it can be read. See the [Keycloak Admin REST user representation](https://www.keycloak.org/docs-api/latest/rest-api/index.html#UserRepresentation).

For example, an operator can allow only the organization's dedicated photo path:

```yaml
koinon:
  identity:
    profile_sync:
      worker_enabled: true
      photo_origins:
        "https://people.example.com":
          - /directory/photos/
```

Replace the example with an installation-owned host. The picture request is anonymous: no directory bearer token, session cookie or ambient proxy credentials are forwarded. Redirects, URL credentials, query strings, fragments and paths outside the allowlist are rejected. The default allowlist is empty. A host requiring separate photo authentication needs an explicitly supported integration; adding a URL does not forward the Keycloak credential.

### Microsoft Entra ID

The current connection uses application credentials and the configured Graph `.default` scope. User reads select company name, title and department through the verified Entra object ID. `User.Read.All` supports the required user fields; actual administrator consent must exist. See [Microsoft Graph user reads](https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0).

User photos use the fixed Graph photo endpoint. Its documented application permissions include `ProfilePhoto.Read.All` and the broader `User.Read.All`; Azure AD B2C photo retrieval is documented as unsupported. The connection's permission display is a configuration requirement, not a live consent check. See [Microsoft Graph photo permissions](https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0).

The Graph v1 manager endpoint currently documents application permissions as unsupported. Select **Verified sign-in claims** with a configured stable manager claim, or **Managed locally**. The app-only connection does not implement delegated manager consent or an undocumented expansion workaround. See [Microsoft Graph manager permissions](https://learn.microsoft.com/en-us/graph/api/user-list-manager?view=graph-rest-1.0).

### Google Workspace

The existing directory adapter requests `admin.directory.user.readonly` and `admin.directory.group.readonly` using the configured service account and delegated administrator. Approve only the scopes needed by this integration through the Workspace domain-wide delegation process, and ensure the delegated administrator has the corresponding authority. See [Google's delegation procedure](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority).

Presentation uses the user's stable ID, name, primary organization and thumbnail photo. Choose whether the department label comes from the primary organization's department or `orgUnitPath`. Multiple ambiguous primary organization entries are not silently reduced to the first. Google organizational units are service-administration labels; this option does not import an HR hierarchy. See the [Google user resource](https://developers.google.com/workspace/admin/directory/reference/rest/v1/users) and [photo endpoint](https://developers.google.com/workspace/admin/directory/reference/rest/v1/users.photos/get).

A provider-reported manager email is resolved through a bounded lookup in that configured directory. The returned stable ID and customer must match before an existing local provider-bound person can be linked. This is not email-based account linking. A missing or unresolved manager remains explicitly unavailable.

## Choose sources in administration

Open **Settings**, choose **People**, then **Directory settings**. Choose the **Corporate profiles** tab, then select the configured identity provider. The neighboring **Directory visibility** tab controls who can browse people and reporting lines; it does not enable profile synchronization. Managing this section requires organization-level `members:write` and `identity:manage`; workspace administration is insufficient.

1. Select **Enable profile updates** when this provider should maintain profiles. With it unchecked, saved settings stay available for review while updates are paused.
2. Under **Update method**, choose **Verified sign-in only** to keep the existing job-title, unit and manager claim mappings, or **Directory sync and field sources** to add directory observations between sign-ins.
3. In directory mode, choose **Corporate directory** or **Personal profile** for display name and photo. Choose **Corporate directory**, **Verified sign-in claims** or **Managed locally** for each position field. A periodic directory run cannot refresh an old claim's observation time.
4. Set the refresh interval between 5 and 1,440 minutes; the default is 15 minutes. Decide whether members may use their saved personal name and photo for this organization.
5. For Keycloak, supply the actual attribute names beside the selected sources. For Google, select the department source. Entra's unsupported app-only manager choice is disabled; use a verified manager claim or local management.
6. Select **Save profile settings**, then review **Saved configuration capabilities**. This list describes field support and required permissions for the saved policy. It does not prove provider consent or successful synchronization.

The installation forwards only approved, bounded presentation claims after native identity validation. The default names are `job_title`, `title`, `unit_external_key`, `department` and `manager_external_subject`; an operator can add up to 32 safe flat names with `koinon.identity.presentation_claims.extra_names`. Choosing a custom claim in the mapping does not make an unapproved claim available. Validated bearer tokens use their trusted issuance time for observation freshness; repeated requests with the same or an older token do not make a claim newly observed. API tokens and MCP credentials never supply external identity claims.

Local positions stay locally managed until an administrator explicitly reconnects their managed fields. Department labels do not create organizational units. Existing same-provider unit references can resolve to the organization's configured structure; unknown labels are not an authorization or hierarchy import.

Disabling the mapping stops its presentation and claims observations. Selecting **Verified sign-in only** disables the directory overlay while retaining the verified-claim mapping when **Enable profile updates** remains checked. Stored snapshots and personal preferences are retained; disabling a source does not erase the personal profile.

## Review your organization presentation

Open **Your account**, then **Profile & preferences**. **Organization presentation** shows the effective name/photo, source, provider, status and last synchronization. **Profile source details** separates each field's status and observation time.

If personal overrides are allowed, choose the name and photo to use and select **Save presentation**. This changes only the selected organization. An enforced corporate policy hides the override controls; it does not delete saved personal values.

**Sync now** requests a refresh of the already verified provider binding. A queued or running response is not a successful sync. **Refresh status** reads the stored result without making a new provider request. Administrators can request a refresh for an admitted selected person with the required organization permissions; they cannot supply an arbitrary external user ID or photo URL.

## Understand status and recovery

| Status | Meaning and next step |
| --- | --- |
| Not configured | No active directory policy applies. Review the selected organization and saved mapping. |
| Not bound | A policy exists but a verified source relationship is missing. Complete the matching sign-in; do not guess a link from an email address. |
| Queued or running | Refresh work has been admitted or claimed. Inspect status before requesting more work. |
| Current | Selected synchronizable fields have current or explicit-empty observations for the admitted provider and mapping. Unsupported, unavailable or not-yet-observed selected fields prevent this status. |
| Stale | A previous observation cannot establish the current configuration or freshness. Review policy changes and the next refresh result. |
| Unavailable | A provider, field or permission failure prevented an observation. Correct the connection or source configuration and request a new refresh. |
| Conflict | More than one source relationship cannot be safely resolved. An administrator must review the configured binding; no provider wins by iteration order. |

An empty provider field, an unsupported field and a failed request are different outcomes. A field's last successful observation must not be presented as a new successful read after failure. Current membership, provider/mapping revisions and lease ownership are rechecked before an observation is applied. Corporate presentation never changes roles, grants or API token bounds.

A transient request failure can retain values from the same still-admitted source with the old synchronization time and an unavailable status. Permission, account, identity and binding failures clear the affected corporate presentation. An unusable company source does not silently select a personal photo instead. Explicitly disabling the policy is a separate administration decision.

For a source conflict, review the intended corporate mapping and existing managed position source, correct the conflicting configuration and complete a new verified sign-in. A manual refresh does not choose a winner or erase the conflict. The original personal profile and unresolved corporate observations remain separate.

## Use the typed SDKs

These helpers use the same tenant-scoped endpoints as the interface. Self operations apply current membership, profile permissions and credential bounds. Corporate mapping administration and refreshing another person require the ordinary verified-identity gates; an administrator's personal token cannot bypass them.

### Python

```python
from koinon_sdk import KoinonClient, OrganizationPresentationInput

async def use_personal_presentation(client: KoinonClient, tenant: str) -> None:
    current = await client.organization_presentation(tenant)
    if not current.allow_personal_overrides:
        raise PermissionError("This organization requires corporate presentation.")
    await client.update_organization_presentation(
        tenant,
        OrganizationPresentationInput(
            expected_revision=current.revision,
            name_mode="personal",
            avatar_mode="personal",
        ),
    )
    refresh = await client.refresh_organization_profile(tenant)
    print(refresh.status)
```

### TypeScript

```typescript
import {KoinonClient} from '@fireflyframework/koinon-sdk';

export async function usePersonalPresentation(client: KoinonClient, tenant: string): Promise<void> {
  const current = await client.corporateProfiles.presentation(tenant);
  if (!current.allow_personal_overrides) {
    throw new Error('This organization requires corporate presentation.');
  }
  await client.corporateProfiles.updatePresentation(tenant, {
    expected_revision: current.revision ?? 0,
    name_mode: 'personal',
    avatar_mode: 'personal',
  });
  const refresh = await client.corporateProfiles.refreshSelf(tenant);
  console.log(refresh.status);
}
```

### Java 21+

```java
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.CorporateProfileRefreshInput;
import org.fireflyframework.koinon.sdk.model.OrganizationPresentationInput;
import org.fireflyframework.koinon.sdk.model.ProfilePresentationMode;

public final class PresentationExample {
  public static void usePersonalPresentation(KoinonClient client, String tenant) {
    var api = client.corporateProfiles(tenant);
    var current = api.presentation();
    if (!Boolean.TRUE.equals(current.allowPersonalOverrides())) {
      throw new IllegalStateException("This organization requires corporate presentation.");
    }
    api.updatePresentation(OrganizationPresentationInput.empty()
        .withExpectedRevision(current.revision())
        .withNameMode(ProfilePresentationMode.PERSONAL)
        .withAvatarMode(ProfilePresentationMode.PERSONAL));
    var refresh = api.refreshSelf(CorporateProfileRefreshInput.empty());
    System.out.println(refresh.status());
  }
}
```

Request a refresh only as an explicit action; the clients do not retry it after an ambiguous response. A `409` preference conflict requires reading the latest revision and reviewing the intended change. Refresh bodies are strict empty objects: the server selects the admitted provider identity. Workspace filters remain part of the request scope.

When updating a corporate mapping through the SDK, omitting `profile_sync` preserves the policy, an explicit `null` disables directory sync, and an object supplies the replacement policy. Preference fields differ: omit an unchanged mode; explicit null is invalid. Java's mapping DTO provides `omitProfileSync` and `clearProfileSync` for those separate decisions. See the [complete API and SDK reference](../reference/sdk-api.md) for all four profile helpers and mapping operations.

## Deployment and acceptance

Apply native migration `koinon_0023_ciam_profiles` through the privileged migration job, then provision only the intended runtime table permissions. Existing personal profiles are not rewritten. The native pyfly context owns the synchronization services, repositories, leases and scheduled work; API configuration does not create a second polling process or database pool.

The interval is a scheduling policy, not a freshness guarantee during downtime or provider failure. The scheduler checks every 15 seconds and processes at most 25 items per pass, claiming only the next pair before executing it. The next interval starts after the observation completes. All replicas must share the configured primary datasource and the same intended corporate connection. `worker_enabled: false` pauses the worker, including work admitted by **Sync now** or sign-in; queuing a request does not process it without that worker.

Profile work requires current effective membership. A user admitted only through an expired corporate access observation waits for the existing access-verification path to renew that authority. Profile synchronization does not renew access observations or create grants to keep its own work running. Manual membership and corporate-group access retain their separate policies.

Source tests and controlled provider transports do not establish real tenant consent, live photos or deployment acceptance. Qualify the actual provider with an authorized test account, observe a real change, switch organizations, revoke access and verify the resulting status and private-photo behavior. Keep those results separate in the [qualification record](../operations/qualification.md).

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
