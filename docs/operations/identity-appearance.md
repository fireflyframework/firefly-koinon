# Identity and appearance

Administrators can adapt the installed product to their organization by opening **Settings** and selecting **Identity & appearance** in the **Organization** group. Change the product name, assistant name, light and dark logos, assistant symbol, browser icon and both color palettes. The preview changes as you edit; other screens change only after **Save changes** succeeds. **Discard changes** restores the last saved values.

Organization changes require `settings:write` for the organization. Workspace administration alone does not grant this permission. Existing catalog, knowledge, query or chat scopes allow reading the identity only within an authorized organization. Branding never grants knowledge access or changes source attribution.

## Configure the identity visually

1. Open **Settings** and select **Identity & appearance** in the **Organization** group. Confirm the organization shown below the heading.
2. In **Identity**, enter the product and assistant names. Upload or drop each logo/icon onto its own field. Light and dark assets have separate previews; transparent areas use a checkerboard.
3. Open **Colors**. Enter a brand color and choose **Apply to both themes** to generate readable action and link colors without saving. Then select **Light** or **Dark** to refine each token. The readability panel reports the measured ratios.
4. Switch the live preview between **Chat**, **Navigation** and **Sign-in**. On mobile, expand **Preview your identity** when needed; it does not occupy the form by default. The sign-in preview uses the installation identity, as explained below.
5. Choose **Save changes**. **Discard changes** returns to the saved record. If another administrator saves first, reload the settings before submitting another update.

[![Identity editor with contextual preview](../assets/screenshots/identity-editor.png)](../assets/screenshots/identity-editor.png)

[![Color editor and measured contrast](../assets/screenshots/identity-colors.png)](../assets/screenshots/identity-colors.png)

The screenshots show the built interface with controlled example data. The example customer name is not the default product identity. See the [visual walkthrough](../guides/interface-tour.md) for the surrounding organization, library and account flows.

## Installation defaults and organization overrides

Set installation defaults under `koinon.branding` in the configuration supplied through `KOINON_CONFIG_FILE`:

```yaml
koinon:
  branding:
    product_name: Northstar Knowledge
    assistant_name: Northstar
    palette:
      light:
        surface: '#ffffff'
        canvas: '#f8fafc'
        text: '#172033'
        muted: '#475569'
        line: '#cbd5e1'
        action: '#2563eb'
        action_text: '#ffffff'
        accent: '#1d4ed8'
```

Unspecified deployment fields use the shipped Firefly defaults. Manrope remains the interface typeface. Names may contain 1–64 printable characters. Identity settings are presentation metadata, not instructions sent to a model. New export/share reviews retain an immutable identity snapshot, so later renaming does not relabel an already reviewed transcript; historical reviews without an identity remain explicitly unrecorded.

The sign-in page uses the installation identity, available through the public, read-only `GET /api/v1/branding/defaults` endpoint. It does not reveal an organization's settings before authentication. After sign-in, the selected organization's saved override takes precedence. The standalone application updates its browser title and icon. When a renamed product has no custom logo, its name is displayed as text rather than retaining the original product logo.

**Use deployment defaults** previews the installation identity. Save to restore inheritance. Resetting preserves the revision counter, so an older open editor cannot overwrite a newer change. A conflict requires reloading before another save.

## Images and colors

Upload PNG, JPEG or WebP images, up to 256 KiB each, with neither dimension exceeding 2048 pixels. Animated images, SVG, remote image URLs and executable formats are rejected. The server decodes and rewrites accepted images as metadata-free PNGs and checks the normalized size too. Deployment configuration uses the same validated `data:image/...;base64,...` representation. Small identity assets are stored with the revisioned identity record; this does not change knowledge-file object storage or its retention policy.

Configure the light and dark palettes independently. All colors use six-digit hex notation. Text, secondary text and link colors must meet 4.5:1 contrast against both surface and canvas; primary-button text must meet 4.5:1 against its button color. The server enforces these checks as well as the editor. Layout, interaction sizes, legal notices and semantic status indicators remain part of the product's design system.

## API and SDKs

The API supports these operations:

| Operation | Route |
| --- | --- |
| Installation identity | `GET /api/v1/branding/defaults` |
| Effective organization identity | `GET /api/v1/tenants/{tenant_id}/branding` |
| Save override | `PUT /api/v1/tenants/{tenant_id}/branding` |
| Restore inheritance | `POST /api/v1/tenants/{tenant_id}/branding/reset` |

Writes include `expected_revision`. Saving also includes a `branding` object; reset includes only the expected revision. Responses record the effective identity, its origin and its current revision. Updates are audited without including image bytes in audit events.

TypeScript exposes `client.branding.defaults()`, `.get(tenantId)`, `.update(tenantId, input)` and `.reset(tenantId, input)`. Python exposes `branding_defaults()`, `organization_branding(tenant_id)`, `update_organization_branding(tenant_id, input)` and `reset_organization_branding(tenant_id, input)`. Java exposes `client.branding()` for installation defaults and `client.branding(tenantId)` for organization operations. All use generated DTOs.

## Embedded applications

The Angular workbench accepts an optional typed `branding` input and emits its effective identity through `brandingChange`. An explicit host identity takes precedence over organization settings in that embedded instance. The custom element accepts the same object as its `branding` JavaScript property. Use `brandBase` for the location of the shipped logo and Manrope assets.

Each workbench owns its identity service and CSS variables inside its shadow root. Differently branded workbenches can coexist without changing the host page's styles, title or favicon. The standalone management application handles its own document metadata through the identity event. A host application can choose whether to do the same.

## Persistence and rollout

Native migration `koinon_0019_org_branding` adds the organization identity table after migration 0018. Apply it through the normal reviewed deployment migration procedure before deploying the new backend. Organization records use revision checks and retain update actor/time; restoring inheritance retains the row instead of deleting its revision history. Legal attribution remains Firefly Software Foundation under Apache 2.0.
