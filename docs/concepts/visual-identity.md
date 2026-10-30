# Visual identity

koinon uses the Firefly family identity: Manrope, a charcoal and paper palette, and amber accents. The documentation uses the same family lockup as the product: the Firefly wordmark, a divider and the koinon wordmark.

## Product positioning

Lead with **Your corporate brain.** The product name remains **koinon**, written in lowercase. The positioning describes its role: bringing organizational documents, datasets and reviewed knowledge together, with sources people can inspect.

Explain that role through concrete actions: find a document, query a dataset, ask a question, inspect its evidence or review a proposed update. Keep the familiar **Library**, **Chat** and **Settings** labels. Integrators can use the same knowledge capabilities through the headless API, typed SDKs or embedded components.

Distinguish reviewed knowledge from a model’s proposal. Proposed changes require human approval; the positioning must not imply that koinon independently decides what the organization knows. Describe access controls and provenance in terms of their actual behavior, and keep runtime qualification statements explicit.

Use the existing linked-o symbol and Firefly family lockup to express the idea. Do not replace them with a brain illustration or change the typography, colors or logo geometry to support the positioning.

## Logos

The navbar uses the [reversed family lockup](../assets/firefly-koinon-lockup.svg) on a charcoal background in both light and dark appearances. It remains visible on narrow screens, alongside the menu and search controls. The [product symbol](../assets/koinon-symbol.svg) is the favicon.

Use the supplied SVGs without changing their proportions, letter shapes or colors. Keep the Firefly endorsement and divider together. Logo lettering is outlined so it does not depend on a browser font download.

## Typography

All documentation text uses Manrope, including navigation, headings, buttons, search, tables, code examples and diagrams. Font files are served with the site; reading the documentation does not require Google Fonts or another font service. The variable font supports weights 200–800 and includes Latin, extended Latin, Greek, Cyrillic and Vietnamese subsets.

Body text uses weight 400. Navigation and headings use stronger weights from the same font. Code examples retain whitespace, horizontal scrolling and numeric alignment. The font is distributed under the [SIL Open Font License](../assets/OFL.txt).

## Colors and interaction

| Role | Color | Use |
| --- | --- | --- |
| Charcoal | `#10110f` | Navbar and dark surfaces |
| Paper | `#f3f1eb` | Reading surfaces and text on charcoal |
| Ink | `#272820` | Body text on paper |
| Amber | `#ffb34a` | Brand accent and links on dark surfaces |
| Gold | `#855414` | Links on light surfaces |

The appearance control switches between light and dark reading surfaces. Keyboard focus, search and the navigation drawer remain available at mobile widths. The footer carries the foundation copyright, Apache License 2.0 and a small animated heart. Reduced-motion preferences disable its animation and interface transitions.

## Product layout and component boundaries

The product keeps primary destinations in the top navigation. Chat has one contextual sidebar for conversations and folders; organization, theme and account controls stay in the header. The knowledge search field belongs to Library. On narrow screens, primary navigation and conversation history use separate drawers with keyboard focus management.

A one-line composer is 44px high with desktop controls; touch controls keep 44px targets. It grows for multiline input and file previews. Amber marks the enabled send action, while disabled controls use neutral colors. The chat reading column uses the canonical 760px token. Tables keep exports in their footer, and evidence panels share the same spacing and border tokens.

The workbench's layout helpers use `workbench-` class names. Component-local empty, error and field states must not inherit a parent component's panel layout. Keep reusable component styles scoped to the component, and share tokens rather than global utility selectors with visual side effects. Review integrated states as well as isolated component previews: an isolated preview cannot reveal style collisions inside the workbench.

## Maintain the site

Run these commands from the repository root:

```bash
python -m venv .venv-docs
.venv-docs/bin/python -m pip install -r docs/requirements.txt
.venv-docs/bin/mkdocs serve --strict
```

For a production build, use `.venv-docs/bin/mkdocs build --strict`. The configuration is in `mkdocs.yml`; site styles, font files and logo assets are in `docs/assets`. Small template overrides in `docs_theme/partials` provide the accessible logo, source link and copyright footer. Keep those overrides small so upgrades to Material for MkDocs remain straightforward.

Before publishing, check a wide screen and a narrow screen in both appearances, search, keyboard navigation, logo and font loading, footer links and reduced motion. A successful documentation build validates the site structure; it does not qualify the product runtime.
