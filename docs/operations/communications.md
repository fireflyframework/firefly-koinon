<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Communications and invitations

Use in-app notifications to follow invitations and changes to your access. For installation fields and provider setup, see [communications configuration](../reference/communications-configuration.md). Email is available only when the operator has configured a supported provider, a verified sender and the installation's canonical public address. A disabled, dummy or incomplete provider does not count as a successful delivery.

## Check recipient eligibility

Directory synchronization is optional for sign-in, in-app notifications, knowledge and chat. Email has separate recipient requirements. A configured provider or an email address in a profile does not satisfy them.

| Recipient workflow | Required source of eligibility |
| --- | --- |
| Administrator summaries and supported administrative emails | A current authoritative directory recipient, or an [operator-approved administrator delivery contact](../reference/operator-delivery-contacts.md) with genuine signed identity binding, valid expiry and current event-specific authority. |
| Ordinary optional summaries | The existing directory-backed recipient lane and current membership; operator contacts do not add a general sign-in-email fallback. |
| Email invitations | The selected authoritative directory identity and address; a delivery contact does not create an invitation identity or role. |
| Initial welcome | The separately configured welcome workflow; a welcome-only contact does not authorize later recurring summaries. |

An installation operator can provision, renew or revoke an administrator contact through the [native operator procedure](../reference/operator-delivery-contacts.md), using its separate reviewed database role. An organization administrator cannot create that authority by typing an address into Settings. Check pending sign-in, expiry, revocation and current role eligibility before enabling a schedule. Sign-in does not extend the approved lifetime. An expired contact needs an explicit revision-checked renewal using a fresh authoritative observation.

Follow [the configuration lifecycle](../guides/configuration-lifecycle.md#6-configure-email-eligibility-before-schedules) when changing a sender, provider or schedule. Previewing the actual message is passive; an explicitly authorized native diagnostic queues a new event through the worker. Neither action replays an unknown welcome or establishes mailbox receipt.

## Invite an existing organization account

Open **Settings**, **Access**, **Invite person**. Choose a connected identity directory, search for the intended person and select a directory result. The server verifies the recipient's immutable directory identity and delivery address. An email address entered or selected in the browser never establishes identity.

Choose the organization or a workspace you administer, then a role and expiration. Workspace access grants access to shared knowledge in that workspace. Personal conversations, folders and memory stay private. The review shows the exact recipient and access scope, plus the email generated from the installation's real template. Inspect its HTML or plain-text view before choosing **Send invitation**.

Sending queues an invitation. **Accepted by email service** means the provider accepted the message, not that it reached an inbox. **Delivered** requires delivery evidence. **Outcome unknown** means the service cannot safely decide whether a send succeeded; it is not automatically replayed. Delivery history offers a retry only when the server marks it safe.

Under **Email invitations**, filter by status, revoke a pending invitation or resend when the server permits it. Grant changes require revoking the old invitation and creating a new one. Reopening an already accepted invitation cannot restore a membership that an administrator later removed.

The email link contains a noncredential invitation UUID. The recipient signs in with the existing organization account to accept or decline. A different account cannot inspect its details. The native acceptance page works without the Angular application. The separate **Create legacy invitation link** action preserves the existing bearer-link workflow and explicitly warns that anyone holding that private link may accept after sign-in.

## Read your inbox

Open the notification bell or **Your account**, **Notifications**. Choose **All notifications** or **Unread**, then select a type if needed. Filters apply immediately and pagination reads results from the server. Mark a specific notice read or open an available invitation/workspace action. A confirmed read refreshes the bell's count; in the unread view it also refreshes the list. If the count cannot be loaded, the bell shows an availability warning instead of suggesting that there are no unread notices.

An access-removal notice remains in your own inbox after the corresponding role is removed. A notice does not grant access to its target; current authorization is checked again when you open it. In-app notices remain usable when email is disabled. Reading a notice does not confirm email delivery.

Required security and access notices remain enabled. They are separate from optional summaries and personal channel preferences. Tokens, approval credentials and private provider errors never appear in notification content.

## Configure a weekly or monthly summary

Open **Notification preferences**. Choose an allowed summary frequency or **Off**. For a weekly summary, choose a weekday and local send time. For a monthly summary, choose a day from 1 to 31 and a local send time. Shorter months use their last day; choosing the 31st does not skip February.

Choosing a cadence enables the optional email summary channel when email is available. You can change the summary inbox/email channels separately; loading a saved email opt-out never enables it again.

The schedule uses your profile's IANA time zone. **Preview next summary** computes the next local time and UTC instant without saving. At a daylight-saving gap, the server chooses the first valid minute; at an overlapping hour it sends once, using the earlier occurrence. Save preferences only after reviewing the next run.

Summaries contain permission-filtered activity belonging to the recipient, not questions, answers, conversation text or private memory. Unavailable historical measurements remain unavailable rather than becoming invented zeroes. Optional summaries can be turned off without disabling mandatory security notices.

Choose **Use organization or installation language** to inherit the configured language, or explicitly select English or Spanish. The effective email language and its origin are shown. An implicit English profile default does not override a Spanish installation. Custom branding applies to the email's logo, typography and palette; every HTML/text email retains **Powered by koinon** and the Firefly Software Foundation copyright, together with the originating organization and workspace when applicable.

**Preview summary email** renders the actual HTML and plain-text message from your draft preferences and a past reporting window. It neither saves preferences nor sends a message. The reporting picker uses explicit UTC date boundaries, includes the start and excludes the end, and groups daily observations in your profile time zone. It accepts at most 366 days and never forecasts future usage.

## Review knowledge and MCP activity

Open the existing **Activity** view. Choose a past reporting window and **View summary** to see your own knowledge created, updated and consulted, current authorized projects, and recorded MCP requests and tool calls. The processing job list remains below the summary.

Coverage is explicit. Missing historical observations and unavailable model usage remain unavailable. Requests are distinct from tool calls, latency covers tool execution, and external clients' token consumption is not observed. Recorded cost retains its supplied currency and precision. Current organization administrators with the required audit and activity permissions can choose the administrator audience; the server checks current authority again and never accepts an arbitrary subject from this screen.

## Administer communications

Open **Settings**, **Communications**. **Email service** shows readiness and operator configuration issues without exposing provider credentials. **Policies** selects among operator-verified senders, required channels and allowed optional summary schedules. Administrators cannot assert sender verification or supply arbitrary sender addresses from this screen.

Under **Administrator summaries**, independently enable daily, weekly and monthly schedules, each with its own local send time and calendar day. These apply to current organization administrators with current audit authority. In personal notification preferences, an administrator can inherit the organization policy, enable the optional summaries or turn them off. This never disables required security and access notices.

**Delivery history** supports server-side status, event and date filters with pagination. Open a record for its bounded status explanation and attempt timestamps. Current scope and membership restrictions still apply to administrator API tokens.

The operator sets `koinon.public_url` to the canonical installation origin; invitation URLs never come from a request's Host header. Keep the default native acceptance route unless a same-origin custom client route has actually been deployed. Serve all emitted frontend chunks so optional views remain reachable after a rollout.
