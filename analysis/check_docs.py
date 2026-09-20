"""Check rendered documentation tables, article links, and local assets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


@dataclass
class Table:
    line: int
    rows: list[int] = field(default_factory=list)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.issues = []
        self.in_article = False
        self.paragraph = None
        self.tables = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "article":
            self.in_article = True
        if tag == "a" and self.in_article and "href" in attributes:
            self.links.append((self.getpos()[0], attributes["href"]))
        if tag in {"img", "script"} and "src" in attributes:
            self.links.append((self.getpos()[0], attributes["src"]))
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.links.append((self.getpos()[0], attributes.get("href", "")))
        if not self.in_article:
            return
        if tag == "p":
            self.paragraph = (self.getpos()[0], [])
        if tag == "table":
            self.tables.append(Table(self.getpos()[0]))
        if tag == "tr" and self.tables:
            self.tables[-1].rows.append(0)
        if tag in {"th", "td"} and self.tables and self.tables[-1].rows:
            try:
                span = int(attributes.get("colspan", "1"))
            except ValueError:
                span = 0
            self.tables[-1].rows[-1] += span

    def handle_data(self, value):
        if self.paragraph is not None:
            self.paragraph[1].append(value)

    def handle_endtag(self, tag):
        if tag == "p" and self.paragraph is not None:
            line, parts = self.paragraph
            rows = "".join(parts).splitlines()
            if sum(row.lstrip().startswith("|") for row in rows) >= 2:
                self.issues.append((line, "table-like paragraph did not render as a table"))
            self.paragraph = None
        if tag == "table" and self.tables:
            table = self.tables.pop()
            if table.rows and len(set(table.rows)) != 1:
                self.issues.append((table.line, f"inconsistent table column counts: {table.rows}"))
        if tag == "article":
            self.in_article = False


def check_site(site):
    site = Path(site).resolve()
    pages = {}
    for path in sorted(site.rglob("*.html")):
        page = Page()
        page.feed(path.read_text(encoding="utf-8"))
        pages[path] = page
    issues = []
    if not pages:
        return [f"{site}: no generated HTML pages; build the site first"]
    for path, page in pages.items():
        for line, message in page.issues:
            issues.append(f"{path.relative_to(site)}:{line}: {message}")
        for line, href in page.links:
            link = urlsplit(href)
            if link.scheme or link.netloc or href.startswith("/"):
                continue
            target = (path.parent / unquote(link.path)).resolve() if link.path else path
            if target.is_dir():
                target /= "index.html"
            message = None
            if not target.is_relative_to(site) or not target.is_file():
                message = "missing local target"
            elif link.fragment and target in pages and unquote(link.fragment) not in pages[target].ids:
                message = "missing fragment"
            if message:
                issues.append(f"{path.relative_to(site)}:{line}: {message}: {href}")
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?", type=Path, default=Path("site-mkdocs"))
    args = parser.parse_args()
    issues = check_site(args.site)
    if issues:
        print("\n".join(issues))
        return 1
    print(f"Rendered documentation checks passed: {args.site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
