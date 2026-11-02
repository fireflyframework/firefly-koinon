# Communications installation configuration

Communications use native pyfly notifications, templates, scheduling and primary database transactions. The installation owns the transport and verified sender allowlist. Organization administrators select an allowed sender, branding, language and summary policy; they cannot configure arbitrary SMTP hosts, credentials, HTML or subject templates.

Use the product's pinned pyfly version, 26.10.32 in this release. Apply the native communications migration and provision its runtime table privileges before enabling communications. Run the complete worker role separately from API processes. The API never starts the communications scheduler.

Directory synchronization is optional. When an installation uses basic native SSO without directory application permissions, use [operator-approved delivery contacts](operator-delivery-contacts.md) for durable, revocable administrator email targets and a new native delivery diagnostic. Inbox access and SSO do not depend on directory availability. Invitation recipient discovery remains a separate directory-dependent capability.

## Enable inbox and select a transport

```yaml
koinon:
  public_url: https://knowledge.example.org
  communications:
    enabled: true
    default_locale: en-US
    verified_senders:
      - id: organization-mail
        display_name: Knowledge team
        address: knowledge@example.org
pyfly:
  notifications:
    enabled: true
    email:
      provider: azure-communication-email
      from: knowledge@example.org
      azure:
        credential-mode: managed-identity
        endpoint: https://example.communication.azure.com
        timeout: 10
        poll-timeout: 30
        poll-interval: 1
```

The Azure provider additionally requires the native `pyfly[notifications-azure]` extra, an explicitly selected managed identity with email sending authority, and a sender/domain approved by the email service. Setting `verified_senders` records the operator's approved choices; it does not verify DNS, configure an email domain or prove mailbox delivery. No infrastructure is created by this configuration.

Native SMTP, SendGrid and Resend are also supported through their native pyfly configuration. SMTP uses certificate verification and an explicit TLS mode; do not disable certificate verification. Credentials belong in installation secret configuration. Organization policies contain sender IDs, never credentials.

`KOINON_PUBLIC_URL` overrides `koinon.public_url`. This must be one canonical origin, with HTTPS outside loopback development. Links never derive their authority from `Host` or forwarded headers. The default invitation path is `/auth/invitations/email/{uuid}` and works without a frontend bundle or MCP being enabled. A different fixed same-origin `acceptance_client_path` is an operator option only when that client route exists.

Communications encryption uses the existing installation identity master key. Preserve that key and the primary database in backups. Recipient references, directory cursors and stored MIME payloads use separate cryptographic contexts. No email address, link UUID or browser-supplied directory claim grants membership.

## Delivery readiness and outcomes

When communications are enabled, required security and access changes admit an in-app notification in the same primary transaction as the mutation. Missing event-recorder bindings fail application preflight. Disabled email, a dummy provider, missing real transport, or absent approved sender produces suppressed email history; the inbox remains available. Enabling email later does not replay that history or backfill digest windows.

`ready` means declared native transport capabilities and approved configuration are present. It does not prove network delivery, sender reputation or mailbox arrival. `sent` means the email service accepted the operation. `delivered` requires a separate proven delivery observation; the submission worker does not infer it. A provider-reported handoff to a recipient mail or protection server does not establish inbox placement. Use the [message investigation workflow](../operations/communications.md#investigate-a-message-that-did-not-arrive) to keep those observations separate. `unknown` means a submission may have happened. Expired sending leases, cancellation, network ambiguity and pending provider operations never become automatic resend permission.

The worker freezes one encrypted payload, stable message ID and SHA-256 before persisting the `sending` fence. Both HTML and complete plain text are passed to native `EmailMessage`; trusted raster logos use native inline CID attachments. A preparation retry cannot replace the payload. Current recipient directory identity, sender, provider revision and relevant authority are checked again before submission. A mutation committed after that boundary may race an already in-flight external operation; email delivery cannot retroactively retract a message.

Invitation resend creates a new explicit attempt after current recipient, original inviter and originating PAT authority checks. Unknown in-flight delivery cannot be resent by the ordinary resend action. Historical committed security notices remain valid when the actor's token later expires.

## Language, branding and summaries

The language order is explicit notification preference, organization communications default, installation communications default, then `en-US`. Supported language families are English and Spanish. Automatic profile locale defaults are not evidence of an explicit notification preference. Responses expose `effective_locale` and `locale_origin` (`user`, `organization`, `installation`, `default`).

Subjects include the validated product name, purpose and authorized organization/workspace. The same catalog, values and actions feed HTML, plain text and preview. Templates escape data and reject header control characters. Every communication retains **Powered by koinon** and **© {year} Firefly Software Foundation**, including custom branding.

Personal summaries are optional and default off. Organization policy controls allowed personal cadences. Administrators may configure up to three distinct administrative schedules in `admin_summaries`, each containing `cadence` (`daily`, `weekly`, `monthly`) and `schedule`. Account preferences may inherit those schedules or opt out with `admin_summaries: false`. Administrative summaries require a current organization administrator assignment and audit authority; they do not introduce a global administrator role.

Schedules contain `local_time` (`HH:MM`), `weekday` (Monday is 0) and `day_of_month` (1–31). They use the profile's IANA time zone. Monthly days clip to the final day in shorter months. A nonexistent local time launches at the first valid minute; a repeated hour uses the earlier occurrence once. Calendar preview exposes UTC/local launch time. Activity email preview separately requires an explicit observed past window and cannot forecast future counts.

Due subscription rows, immutable half-open windows and unique delivery keys prevent restart duplicates. Reconciliation is bounded to 25 organization policies per pass and fails clearly above 1000 effective membership assignments in one policy. Only the most recent due window is admitted after downtime; earlier history is not backfilled. Disabled email advances past the skipped window without queuing a digest. Current access is checked during aggregation and before sending; changed observations invalidate the frozen summary payload.

Summary counts come from `ActivitySummaryReader`. Missing observations remain unavailable, not zero. Tool calls, MCP HTTP requests and tool latency have distinct meanings. External client consumption or model billing is not invented. Project bars use the authorized returned counts and have the same values in plain text.

## Worker bounds and security

The worker's native scheduled tick runs every 15 seconds. It reconciles schedules, admits at most ten due windows and processes at most ten delivery tickets per tick. Claiming, rendering and the complete transport lifetime hold the shared `communications` work admission permit. Communications are the eighth observed worker workload; due digest rows and expired preparation/sending leases contribute demand. The broader worker still needs independent maintenance coverage before scale-to-zero can be qualified.

| Setting | Default | Supported range |
|---|---:|---|
| `lease_seconds` | 120 | 30–600; at least send timeout + 15 |
| `send_timeout_seconds` | 30 | 1–60 |
| `max_attempts` | 3 | 1–10 preparation claims |
| `resend_cooldown_seconds` | 300 | 60–3600 |
| `max_invitation_sends` | 5 | 1–10 explicit sends |
| `allow_entra_guests` | false | Explicit guest delivery policy |

Native browser pages require a matching native session, reject authorization-header credentials, bound form bodies and retain CSRF protection. Own inbox/preferences permit explicitly scoped personal tokens (`notifications:read`, `notifications:write`, with write implying read) and survive membership loss. Email acceptance/decline remain interactive; new administrative communications APIs require current `members:write` authority and the PAT's tenant/workspace ceiling. Activity email preview additionally requires `activity:read` for a personal token.

Initial administrator welcomes have one persisted installation UUID and a unique immutable-identity admission. Brand, domain, release and template changes cannot produce a new automatic welcome. Before a fresh verified identity binding, the welcome is visible in-app with explicitly suppressed email. The first verified native login may complete that initial pending admission only while the real email channel is ready. Disabled and unknown submissions are not replayed automatically.

For welcome before first sign-in, an operator can instead admit a fresh contact observation tied to an
existing exact pending bootstrap identity grant. See [initial administrator welcome](bootstrap-welcome.md)
for the protected-file command, fifteen-minute import freshness, twenty-four-hour delivery boundary,
required live public origin and signed-login association. This initial contact does not itself enable
ongoing email. Administrator summaries and supported administrative notices require a separate verified
directory binding or [operator-approved administrator delivery contact](operator-delivery-contacts.md).
Ordinary recipient and invitation workflows keep their directory requirements.
