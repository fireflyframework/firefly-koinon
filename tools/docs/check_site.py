# Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc.
# SPDX-License-Identifier: Apache-2.0
"""Check generated documentation links, branding and local font assets."""

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self, source: str):
        super().__init__()
        self.links: list[str] = []
        self.anchors: set[str] = set()
        self.logo = False
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.anchors.add(values["id"] or "")
        attribute = "href" if tag == "a" else "src" if tag in {"img", "script"} else None
        if tag == "link":
            attribute = "href" if values.get("rel") in {"stylesheet", "icon"} else None
        if attribute and values.get(attribute):
            self.links.append(values[attribute] or "")
        if tag == "img" and values.get("alt") == "firefly and koinon":
            self.logo = True


def check(root: Path) -> list[str]:
    pages = {path.resolve(): Page(path.read_text()) for path in root.rglob("*.html")}
    failures = []
    if not pages:
        return ["No generated HTML pages found"]
    for path, page in pages.items():
        if not page.logo:
            failures.append(f"{path.relative_to(root)}: family lockup is missing")
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                if url.hostname in {"fonts.googleapis.com", "fonts.gstatic.com"}:
                    failures.append(f"{path.relative_to(root)}: external font dependency")
                continue
            decoded = unquote(url.path)
            target = root / decoded.removeprefix("/firefly-koinon/") if decoded.startswith("/") else path.parent / decoded
            target = target.resolve()
            if target.is_dir():
                target /= "index.html"
            if not target.is_relative_to(root) or not target.is_file():
                failures.append(f"{path.relative_to(root)}: missing local target {link}")
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].anchors:
                failures.append(f"{path.relative_to(root)}: missing anchor {link}")
    fonts = root / "assets/fonts"
    if len(list(fonts.glob("manrope-*-wght-normal.woff2"))) != 6:
        failures.append("Expected all six local Manrope variable font subsets")
    return failures


if __name__ == "__main__":
    site = Path(sys.argv[1] if len(sys.argv) > 1 else "site").resolve()
    errors = check(site)
    if errors:
        raise SystemExit("\n".join(errors))
    print("Documentation links, family lockup and local Manrope assets verified.")
