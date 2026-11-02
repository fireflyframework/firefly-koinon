<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Initial administrator welcome

An installation operator can queue a branded welcome before an initial administrator's first sign-in.
This uses an existing pending direct-Entra bootstrap grant and a fresh, authoritative Microsoft Graph
contact observation. It does not activate the grant, create a principal, or authorize access by email.
Only the existing signed OIDC login flow activates the exact issuer, client, tenant and object identity.

First migrate through `koinon_0035_bootstrap_welcome`, provision the scoped roles, and seed pending
identity grants using `deploy/bootstrap.py --identity-grants-file`. Configure the real native email
provider, an approved sender, the installation branding and locale, and `koinon.public_url` (or
`KOINON_PUBLIC_URL`). Verify that the public origin and SSO entry are live before admitting contacts.
The operator must use its existing authorized directory reads; this workflow requests no new Graph
permission and stores no operator credential in the application.

Create an owner-only JSON file containing one to one hundred observations. Every identity must match
an existing pending grant exactly. The example values below are inert; replace them with authoritative
observations and the installation's exact pins.

```json
[
  {
    "tenant_id": "example",
    "issuer": "https://login.microsoftonline.com/00000000-0000-4000-8000-000000000011/v2.0",
    "client_id": "configured-native-client",
    "entra_tenant_id": "00000000-0000-4000-8000-000000000011",
    "object_id": "00000000-0000-4000-8000-000000000012",
    "email": "admin@example.test",
    "display_name": "Initial administrator",
    "source": "microsoft_graph_v1",
    "account_enabled": true,
    "user_type": "Member",
    "observed_at": "2026-11-01T12:00:00Z"
  }
]
```

Read `/v1.0/users/{object_id}` from Microsoft Graph with `id`, `displayName`, `mail`,
`userPrincipalName`, `accountEnabled` and `userType`. Confirm the exact object, enabled member status
and corporate delivery address. `observed_at` records that actual observation, not an arbitrary date.
Use `mail`, or the authoritative member `userPrincipalName` if `mail` is absent. Import within fifteen
minutes; observations more than thirty seconds in the future are rejected. Keep the file outside Git,
owned by the operator with mode `0600`. Symlinks, oversized input and duplicate identities are rejected.

```bash
python deploy/bootstrap_contacts.py --contacts-file /protected/operator/bootstrap-contacts.json
```

Run this privileged command with the operator/migration datasource, never a web or worker credential.
The whole file is admitted atomically. Runtime roles may read contact receipts and bind only their
canonical-subject column; database guards require the grant's actual consumed subject and active
administrator membership. Runtime roles cannot insert, retarget or delete operator contacts.

The contact address and identity observation are encrypted using the existing communications key.
The shared installation ledger admits one welcome per immutable identity. The normal outbox worker
renders the existing localized HTML and complete plain-text template, branding and fixed foundation
attribution. Its safe setup link contains no password, access token or invitation credential. The
English and Spanish pending-enrollment copy explains that SSO must activate access.

Submission rechecks the exact grant, configured OIDC pins, contact expiry, approved sender and real
provider. The contact is valid until the earlier of grant expiry and twenty-four hours after the
directory observation. A disabled or unavailable email channel records suppression; enabling it later
does not flood an old backlog. Reimporting the same identity does not create another submission or
reset its outcome. `sent` means provider accepted, not mailbox delivered. `unknown` is not automatically
retried. Keep the original receipts when a provider outcome is uncertain.

After signed first login, the grant and existing welcome event associate with the real canonical
`issuer|sub`. An inbox welcome is then created without sending a second email, even across restarts,
branding changes and releases. If the grant expires or the associated administrator membership is
revoked before submission, the welcome is cancelled.

This contact is exclusively for initial welcome. It does not automatically authorize ongoing email.
For recurring administrator summaries and supported administrative notices, configure either the
existing verified directory delivery binding or a separate [operator-approved administrator delivery
contact](operator-delivery-contacts.md). Invitations and ordinary recipient workflows retain their own
directory requirements. No email string is an authentication or authorization authority.

## Check the result without repeating enrollment

Keep the returned welcome identity and delivery history with the installation record. In **Settings**,
**Communications**, inspect the existing event before changing any configuration. A queued event still
needs the normal worker. Provider acceptance and even provider-reported delivery are separate from the
administrator confirming that the email reached their mailbox.

If email was disabled, fix the provider or sender for future communications; do not reseed the
bootstrap grant or reset the welcome admission. If the outcome is unknown, preserve the original
operation and inspect its existing provider evidence. The welcome workflow has no general resend
button. An administrator who has signed in can use the setup documentation and their in-app welcome
without receiving another enrollment email. For a later independent delivery check, use the separately
authorized [administrator-contact diagnostic](operator-delivery-contacts.md#queue-one-new-diagnostic)
after its current eligibility checks. See [message investigation](../operations/communications.md#investigate-a-message-that-did-not-arrive)
for the provider and recipient-side handoff.
