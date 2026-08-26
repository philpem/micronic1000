#!/usr/bin/env python3
"""build.py - render the Micronic-1000 doc Markdown into a single HTML
site, including Mermaid diagram rendering.

Strategy: convert each .md to an HTML fragment with python-markdown,
wrap in a shared template, and load Mermaid.js from a CDN so the
diagrams render client-side (view the HTML in a browser).  If you
prefer fully-offline static SVG, use mermaid-cli (mmdc) instead -
the Makefile documents both.

Dependencies:  python3 -m pip install markdown
Works offline for text; Mermaid requires browser + net to fetch the
CDN JS (or vendor mermaid.min.js locally and override MERMAID_JS).
"""
import argparse
import html
import pathlib
import re

import markdown

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "site-html"
MERMAID_JS = (
    "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
)
STYLE = """
  body{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;
       padding:0 1.2rem;line-height:1.55;color:#1c1c1c}
  pre{background:#f6f8fa;border:1px solid #d8dee4;border-radius:6px;
      padding:.8rem;overflow:auto}
  code{background:#f6f8fa;padding:.1em .3em;border-radius:4px}
  table{border-collapse:collapse;margin:1rem 0}
  th,td{border:1px solid #d8dee4;padding:.4em .7em;text-align:left}
  th{background:#f0f3f6}
  h1,h2,h3{margin-top:1.6em}
  blockquote{border-left:4px solid #ccc;margin-left:0;padding-left:1rem;
             color:#444}
  nav a{color:#0366d6}
"""

def convert_md(path: pathlib.Path) -> dict:
    md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])
    body = md.convert(path.read_text(encoding="utf-8"))
    # run mermaid code fences -> <pre class="mermaid"> so the JS picks them up
    body = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        lambda m: f'<pre class="mermaid">{m.group(1)}</pre>',
        body,
        flags=re.S,
    )
    return {"name": path.stem, "title": path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip(), "body": body}

def wrap(doc: dict, nav: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>{html.escape(doc["name"])} — Micronic 1000</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{STYLE}</style>
<script type="module">
import mermaid from "{MERMAID_JS}";
mermaid.initialize({{ startOnLoad: true }});
</script>
</head><body>
<nav>{nav}</nav>
{doc["body"]}
</body></html>"""

def build_nav_items() -> str:
    links = []
    for f in sorted(ROOT.glob("*.md")):
        fn = "index.html" if f.stem == "README" else f"{f.stem}.html"
        label = f.stem if f.stem != "README" else "index"
        links.append(f'<a href="{fn}">{label}</a>')
    return " | ".join(links)

def main():
    OUT.mkdir(exist_ok=True)
    nav = build_nav_items()
    for md in ROOT.glob("*.md"):
        doc = convert_md(md)
        fn = "index.html" if md.stem == "README" else f"{md.stem}.html"
        (OUT / fn).write_text(wrap(doc, nav), encoding="utf-8")
        print(f"wrote {OUT / fn}")
    print("Done. Mermaid renders on page open (needs net for CDN).")

if __name__ == "__main__":
    main()