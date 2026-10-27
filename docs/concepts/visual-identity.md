# Visual identity

Koinon uses the Firefly family identity: Manrope, a charcoal and paper palette, and amber accents. The documentation uses the same family lockup as the product: the Firefly wordmark, a divider and the koinon wordmark.

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

The appearance control switches between light and dark reading surfaces. Keyboard focus, search and the navigation drawer remain available at mobile widths. The footer carries the copyright holders, Apache License 2.0 and a small animated heart. Reduced-motion preferences disable its animation and interface transitions.

## Maintain the site

Run these commands from the repository root:

```bash
python -m venv .venv-docs
.venv-docs/bin/python -m pip install -r docs/requirements.txt
.venv-docs/bin/mkdocs serve --strict
```

For a production build, use `.venv-docs/bin/mkdocs build --strict`. The configuration is in `mkdocs.yml`; site styles, font files and logo assets are in `docs/assets`. Small template overrides in `docs_theme/partials` provide the accessible logo, source link and copyright footer. Keep those overrides small so upgrades to Material for MkDocs remain straightforward.

Before publishing, check a wide screen and a narrow screen in both appearances, search, keyboard navigation, logo and font loading, footer links and reduced motion. A successful documentation build validates the site structure; it does not qualify the product runtime.
