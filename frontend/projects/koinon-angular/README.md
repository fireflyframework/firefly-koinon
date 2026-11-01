# firefly koinon Angular library

`@fireflyframework/koinon-angular` provides standalone Angular components, a scoped SDK facade, and a knowledge workbench. It is built with Angular partial compilation for use through Angular’s package format. Applications that only need the API can use `@fireflyframework/koinon-sdk` independently.

## Connect a host application

Construct the SDK with a transport that handles your application’s authentication, then provide it through Angular dependency injection:

```ts
import {KoinonClient, FetchTransport} from '@fireflyframework/koinon-sdk';
import {provideKoinonClient} from '@fireflyframework/koinon-angular/workbench';

const transport = new FetchTransport({
  baseUrl: '/bff/api/v1',
  credentials: 'include',
  csrfToken: readCurrentCsrfCookie,
});
const providers = provideKoinonClient(new KoinonClient({transport}), transport);
```

`readCurrentCsrfCookie` is a host-supplied function. For an API bearer integration, use `/api/v1` and an `accessToken` callback that returns a current token scoped to the caller. The library does not persist tokens or take over host authentication, routing, or global CSS.

Import `KoinonWorkbench` in a standalone component:

```html
<ffk-workbench
  [tenantId]="tenantId"
  [workspaceId]="workspaceId"
  [projectId]="projectId"
  [showNavigation]="false"
  [theme]="theme"
  brandBase="/assets/koinon-brand"
  (selectionChange)="selectResource($event)"
  (queryCompleted)="receiveQuery($event)"
  (citationSelected)="openCitation($event)"
  (authenticationRequired)="requestSignIn()"
/>
```

The host can instead set the `client` input. A client change resets scoped state. The server authorizes every requested context; selecting an organization or resource in the component does not grant access.

| Input | Purpose |
| --- | --- |
| `client` | Optional SDK instance; overrides the injected client for this workbench. |
| `tenantId`, `workspaceId`, `projectId`, `resourceId` | Initial authorized knowledge context. |
| `showNavigation` | Show the standalone navigation and personal account controls. |
| `theme` | `light` or `dark`. |
| `brandBase` | URL of the copied canonical brand asset directory. |

Outputs include `selectionChange`, `contextChange`, `queryCompleted`, `citationSelected`, `authenticationRequired`, `signOutRequested`, and `themeChange`. The host handles sign-in, sign-out, and theme persistence when embedding the workbench.

An optional `KOINON_TENANT_RESOLVER` provider lets the host choose an initial organization from the freshly fetched `ContextResponse` and the requested `tenantId`. The resolver runs before the first catalog request; its result must be present in `context.tenants`, otherwise the workbench uses the first authorized organization. The default behavior prefers the explicit input, then the current organization for the same authenticated subject on retry. An empty authorized list clears the current scope without a catalog request. Existing component inputs, constructors, and providers remain compatible.

The management application retains only the selected organization ID in tab storage, scoped by deployment base and authenticated subject, and revalidates it against fresh context. Explicit authorized share and accepted invitation scope takes precedence. Embedded hosts own any persistence policy; the library never reads or writes their URL or browser storage. Listen to `contextChange` to retain selection without feeding every event back into the initial context inputs.

## Optional Chat and Settings

For a Library host, import `KoinonWorkbench`, its injection providers, and optional loader tokens from `@fireflyframework/koinon-angular/workbench`. This entrypoint contains the complete initial Library and its synchronous vocabulary; dialog and provenance vocabulary arrives with those panels. Chat and Settings register their vocabulary before their views render.

The existing root entrypoint remains compatible: it reexports the same component classes and injection tokens, and immediately registers the complete Spanish dictionary for callers of `KoinonI18n.text()`. Hosts that need the complete standalone translation dictionary can keep using the root entrypoint. Do not import root symbols in an initial Library host solely to configure feature loader tokens, because that also loads the complete compatibility dictionary.

Enable optional feature entrypoints with lazy loaders:

```ts
import {KOINON_CHAT_LOADER, KOINON_SETTINGS_LOADER} from '@fireflyframework/koinon-angular/workbench';

const optionalFeatures = [
  {
    provide: KOINON_CHAT_LOADER,
    useValue: () => import('@fireflyframework/koinon-angular/chat/page')
      .then(module => module.KoinonChatPage),
  },
  {
    provide: KOINON_SETTINGS_LOADER,
    useValue: () => import('@fireflyframework/koinon-angular/settings')
      .then(module => module.KoinonSettingsPage),
  },
];
```

The `/chat/page` loader opens conversations without downloading the OpenUI renderer. Evidence downloads from `/chat/evidence` when an answer has an artifact. The existing `/chat` entry point continues to export the same public components for hosts that import them directly. Account, version history, source coordinates, knowledge models, and deployment sections load when opened. Serve every emitted JavaScript chunk alongside the entry scripts so these views remain reachable after deployment.

Operators choose the organization chat agent once by opening **Settings**, selecting **Agents** and using **Organization chat**. Only organization-wide agents can be selected, and clearing the setting makes standard chat unavailable. Every standard Chat initialization reads the authorized organization setting for its current workspace/project; missing, disabled, or inaccessible defaults never fall back to another agent. A host's explicit `chatActions.agentId` / Settings agent trial remains a deliberate per-session override. Stored answer audits keep the actual agent, provider, model, and source snapshots used by each run.

Chat needs the optional OpenUI Angular 0.4 dependency family and Zod 4. The supplied SDK transport supports authenticated JSON requests, binary files, multipart upload, and event streams. Model tools and result access remain server-authorized. Settings controls appear according to the current user’s permissions and the backend’s supported provider descriptors. Model discovery, observed generation, streaming, and tool capability are separate states. An agent the server permits to run while unverified has an explicit trial action. Advanced model options come from the server schema and the selected model API’s supported fields.

## Embedding and presentation

`<firefly-koinon>` exposes the same inputs and DOM custom events through Angular Elements. Set the SDK client as an element property after registration. Do not place access tokens in HTML attributes. The custom element uses Shadow DOM; the host retains its router and document styles. Dialog overlays stay inside the workbench’s shadow root.

Copy `assets/brand` from the built package to your application’s public assets and set `brandBase`. The workbench loads `fonts/manrope-latin-wght-normal.woff2` by default or `fonts/inter-latin-wght-normal.woff2` when its effective branding selects Inter, through the browser FontFace API. Loaded faces are shared by document and asset URL, use a namespaced family, and are released when the final consumer changes font or is destroyed. The font family is assigned only to the workbench CSS variable; host body styles remain unchanged. No font package import is required in the host. Preserve the accompanying font licenses. Use the supplied SVG lockups without reconstructing their lettering.

Profile preferences support English and Spanish interface copy, regional formatting, time zone, and response language. Historical answers retain their saved presentation metadata. Typed decimal strings preserve all digits and trailing zeroes; untyped identifier strings remain unchanged. Downloaded evidence JSON contains the original returned values.

## Build and package checks

From the frontend workspace, run `npm run build:library`. `npm run smoke:consumer` packs the built library and builds a separate Angular consumer using that tarball. Browser embedding tests check input/event behavior and Shadow DOM isolation against hostile host styles. These checks are separate from live-backend acceptance.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Preserve all accompanying third-party notices.

### Custom identity

Organization administrators can manage names, logos and accessible light/dark palettes by opening **Settings**, choosing **Organization** and selecting **Identity & appearance**. The workbench loads the effective identity through the typed SDK. Installation defaults also cover the sign-in screen; organization overrides are read only after authorization.

An embedding application may supply a typed `BrandingValues` object through `[branding]` on the Angular workbench or the custom element's `branding` JavaScript property. Its explicit override takes precedence in that instance. `(brandingChange)` reports the effective identity. Set `font_family` to `Manrope` or `Inter`. The workbench scopes palette variables, font selection and image presentation to its own shadow root; it does not change the host document title, favicon or global styles. Continue to supply `brandBase` for shipped logo/font assets. Legal attribution remains intact.

See [Identity and appearance](../../../docs/operations/identity-appearance.md) for deployment configuration, asset constraints, revision checks and Python, TypeScript and Java API operations.

## Invitations and notifications

Management and the supplied Elements entry point register the optional communications loader. Custom Angular hosts can register the same lazy components:

```typescript
import {KOINON_COMMUNICATIONS_LOADER} from '@fireflyframework/koinon-angular/workbench';

const communicationsProvider = {
  provide: KOINON_COMMUNICATIONS_LOADER,
  useValue: (component: 'trigger' | 'center' | 'email') =>
    component === 'trigger'
      ? import('@fireflyframework/koinon-angular/communications/runtime')
          .then(module => module.KoinonNotificationCenterTrigger)
      : component === 'email'
        ? import('@fireflyframework/koinon-angular/communications/invitations')
            .then(module => module.KoinonEmailInvitationAcceptance)
        : import('@fireflyframework/koinon-angular/communications/inbox')
            .then(module => module.KoinonNotificationCenter),
};
```

Provide the same client and transport through `provideKoinonClient(client, transport)`. If the host overrides a client at runtime, bind its matching transport explicitly:

```html
<ffk-workbench [client]="currentClient" [transport]="currentTransport" />
```

For Elements, set both properties in the same update:

```typescript
Object.assign(document.querySelector('firefly-koinon')!, {
  client: currentClient,
  transport: currentTransport,
});
```

Changing the client without its matching transport clears the previous communications state and disables raw transport requests. The component never reads private SDK fields or reuses a previous actor's transport. In-app notifications remain independent of email provider availability; sending email requires the server's ready capability.

The bell opens **Your account**, **Notifications**. Preferences expose optional weekly/monthly summaries, profile time-zone scheduling and an English/Spanish language override. **Settings**, **Access** separates recipient-bound email invitations from explicitly labeled legacy bearer links. **Settings**, **Communications** exposes email readiness, organization policy and paginated delivery history. Every emitted lazy chunk must be served with the application.

Email links default to the native `/auth/invitations/email/{uuid}` acceptance page, including headless installs. An embedding host can render `KoinonEmailInvitationAcceptance` on its own authenticated UUID route; configure a custom acceptance path only after that route exists. Never convert a legacy bearer token into an email-mode URL.


### Knowledge activity and email previews

The supplied Management and Elements hosts also register `KOINON_ACTIVITY_LOADER`. Embedded hosts can add the same provider alongside their paired client and transport:

```typescript
import {KOINON_ACTIVITY_LOADER} from '@fireflyframework/koinon-angular/workbench';

const activityProvider = {
  provide: KOINON_ACTIVITY_LOADER,
  useValue: () => import('@fireflyframework/koinon-angular/activity')
    .then(module => module.KoinonActivityPanel),
};
```

Register `activityProvider` in the application's providers. The summary loads inside the existing Activity view; the processing job list remains available. Hosts that omit the optional loader keep their existing jobs view. `/activity/window` supplies the shared explicit UTC date-window control, and `/communications/email-preview` supplies the scriptless HTML/plain-text preview used by invitations and personal summary preferences. Each remains a separate lazy package entrypoint.

Activity requests use the current typed client and matching transport pair. Binding a new client without its transport immediately hides prior activity, inbox, preferences, preview and unread values, and prevents a request through the previous actor's transport. The report distinguishes incomplete observations from recorded zeroes and never estimates external clients' token consumption.

See [Communications and invitations](../../../docs/operations/communications.md) for administrator cadence policy, personal opt-out, scheduling and actual rendered summary previews. HTML previews remove navigation targets and active elements in detached inert content, then render in an opaque scriptless frame with no-referrer and a resource-denying content policy. Previewing neither sends email nor changes preferences.
