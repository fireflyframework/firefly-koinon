# Delivery contacts without directory synchronization

Directory synchronization is optional. Inbox notifications work independently of email. Email invitations still require a current authoritative directory recipient; this operator workflow does not turn an address into an invitation identity or create a role.

This increment supports administrator contacts. Ordinary users retain the existing directory-backed recipient lane; it does not introduce a general verified-SSO-email fallback. An installation operator can authorize a delivery contact for an administrator who signs in through the configured native identity provider. This is independent of a directory connector's application permissions. The contact pins the organization, native issuer and client, provider kind and immutable external identity. Direct Entra uses its exact tenant ID and object ID. Keycloak uses its immutable user ID. Brokered Google Workspace uses the existing verified broker, hosted-domain and immutable-subject policy. An email address or Entra object ID is never substituted for the signed OIDC `sub`.

Apply native migration `koinon_0038_operator_contacts` through the ordinary migration workflow, then provision privileges. Do not create the table separately in production. API and worker roles receive contact `SELECT` plus the narrow signed-binding columns; they cannot insert contacts, change addresses, renew, revoke, delete or reset a binding. Use an existing separate operator role for reviewed contact changes:

```sh
python deploy/provision_roles.py --grant --contacts-operator-role approved_contact_operator
python deploy/provision_roles.py --check --contacts-operator-role approved_contact_operator
```

These commands retain the normal configured migration and five runtime datasource inputs. Use a dedicated existing role with `NOINHERIT`, no parent roles, no elevated PostgreSQL flags and no schema/database creation rights. It must be distinct from every runtime/control role. The provisioner grants the exact contact rights, authorization reads on organizations, memberships, managed identity policy and bootstrap activation, policy reads, append-only audit/outbox access and organization row-lock permission. It does not grant membership mutation, outbox mutation, signed-binding updates or unrelated runtime writes. `--check` rejects privilege drift, including inherited roles and forbidden column updates. Credentials remain in protected deployment configuration. Keep the runtime driver and TLS profile when supplying operator credentials to an application context.

## Approve a durable contact

Prepare an owner-only regular JSON file, at most 256 KiB, containing one to one hundred observations. Each observation has `tenant_id`, an `identity` object, the approved `email` and `display_name`, `source`, `account_enabled`, `observed_at` and an explicit `expires_at`. Sources are `microsoft_graph_v1`, `keycloak_admin` or `google_admin`, matching the provider. An explicitly disabled account is rejected. An unavailable account-enabled observation stays `null`; it is not represented as verified enabled.

For direct Entra, the `identity` fields are `kind: "entra"`, the configured `issuer` and `client_id`, `identity_mode: "direct"`, `external_tenant_id` and `external_subject` containing the exact object ID. Do not supply a canonical subject or infer one from an email or object ID. Contact provisioning can reuse an existing immutable bootstrap grant's genuine signed activation; otherwise the contact remains pending until a matching native sign-in by a current organization administrator. It cannot enroll an uninvited account or turn a pending bootstrap administrator into an active administrator.

The directory observation must be fresh, within fifteen minutes, when the operator provisions or renews the contact. That freshness requirement is separate from the authorization lifetime:

```yaml
koinon:
  communications:
    operator_contact_max_lifetime_days: 365
    operator_contact_expiry_warning_days: 30
```

The maximum lifetime accepts 1–3650 days; the warning interval accepts 1–365 days. The operator explicitly chooses an expiry within installation policy. The default allows recurring daily, weekly and monthly summaries without daily operator renewal. Sign-in does not extend the contact, and changing the installation limit does not extend an existing expiry. A more restrictive limit requires renewed contact approval. Address changes need a new authoritative observation and an explicit revision-checked renewal.

```sh
python deploy/communications.py provision --contacts-file /protected/contacts.json
python deploy/communications.py status --contact-id CONTACT_UUID
python deploy/communications.py renew --contact-id CONTACT_UUID --expected-revision 1 --contacts-file /protected/one-contact.json
python deploy/communications.py revoke --contact-id CONTACT_UUID --expected-revision 2
```

Renewal files contain exactly one complete observation. Revocation is terminal. Identity pins and the canonical binding cannot be retargeted. Each operator change is audited as `system:communications-operator`. The native sign-in observer records its own binding action separately.

## Queue one new diagnostic

Run these commands in an API-role operator process. They start a native application context without background schedules or a listener. The worker remains the only sender.

```sh
python deploy/communications.py diagnostic --contact-id CONTACT_UUID --operation-id NEW_OPERATION_UUID
```

The diagnostic accepts no recipient address or subject. It resolves the approved, signed-bound contact and checks current organization administrator authority. It creates a new, plainly labeled diagnostic in the normal outbox and returns its delivery ID and current status. Keep the operation UUID: repeating the same operation observes the same event, including an unknown outcome. A different operation is throttled for five minutes. It never retries an earlier welcome or unknown submission and does not call a provider directly.

Status output separates recipient eligibility, administrator eligibility, transport configuration and expiry state. `pending_signed_login`, `ineligible`, `revoked` or `expired` is not ready for a diagnostic. `expiring` is an operator warning, not automatic renewal. Include these observations in installation monitoring and review them before scheduled-report acceptance; the general transport capability alone does not establish recipient eligibility. A configured provider and a queued event do not establish provider acceptance or mailbox delivery.

The worker rechecks contact revision, expiry, revocation, configuration pins and event-specific authority after rendering and before dispatch. Security and access-removal notices preserve their existing delivery semantics after role loss. Administrative summaries and diagnostics require their current administrative authority; ordinary summaries retain their own membership and scope checks. Contact authorization never replaces those checks. Bootstrap welcome contacts remain a separate welcome-only mechanism.
