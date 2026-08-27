#!/usr/bin/env python3
"""build.py - render the Micronic-1000 doc Markdown into a single HTML
site, including Mermaid and WaveDrom diagram rendering.

Strategy: convert each .md to an HTML fragment with python-markdown,
wrap in a shared template, and load Mermaid.js and WaveDrom from CDNs
so diagrams render client-side (view the HTML in a browser).

Dependencies:  python3 -m pip install markdown
Validation:    cd doc && npm install
Works offline for text; diagrams require browser + net to fetch their
renderers (or locally vendored JavaScript bundles).
"""
import argparse
import html
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

import markdown

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "site-html"
PUBLISHED_DIRS = ("manual", "protocol", "internals")
NAV_GROUPS = (
    ("Manual", "manual/README.md"),
    ("Protocol", "protocol/README.md"),
    ("Internals", "internals/README.md"),
)
MERMAID_JS = (
    "https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.esm.min.mjs"
)
WAVEDROM_SKIN_JS = (
    "https://cdn.jsdelivr.net/npm/wavedrom@3.6.2/skins/default.js"
)
WAVEDROM_JS = (
    "https://cdn.jsdelivr.net/npm/wavedrom@3.6.2/wavedrom.min.js"
)
MERMAID_FENCE_RE = re.compile(
    r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL
)
WAVEDROM_FENCE_RE = re.compile(
    r"^```wavedrom[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL
)
MERMAID_VALIDATOR = ROOT / "validate-mermaid.mjs"
STYLE = """
  body{font-family:system-ui,sans-serif;max-width:none;margin:2rem auto;
       padding:0 1.2rem;line-height:1.55;color:#1c1c1c}
  pre{background:#f6f8fa;border:1px solid #d8dee4;border-radius:6px;
      padding:.8rem;overflow:auto}
  code{background:#f6f8fa;padding:.1em .3em;border-radius:4px}
  table{border-collapse:collapse;margin:1rem 0;width:100%}
  th,td{border:1px solid #d8dee4;padding:.4em .7em;text-align:left}
  th{background:#f0f3f6}
  h1,h2,h3{margin-top:1.6em}
  blockquote{border-left:4px solid #ccc;margin-left:0;padding-left:1rem;
             color:#444}
  nav{font-size:.95rem;margin-bottom:1.5rem}
  nav a{color:#0366d6}
  nav .nav-group{display:inline-block;margin-left:1rem}
  nav .nav-group:first-child{margin-left:0}
  svg{max-width:100%;height:auto}
"""

def published_markdown_paths() -> list[pathlib.Path]:
    paths = [ROOT / "README.md"]
    for directory in PUBLISHED_DIRS:
        paths.extend((ROOT / directory).rglob("*.md"))
    return sorted(paths)


def output_path(path: pathlib.Path) -> pathlib.Path:
    relative = path.relative_to(ROOT)
    if relative == pathlib.Path("README.md"):
        return OUT / "index.html"
    return OUT / relative.with_suffix(".html")


def rewrite_markdown_links(source: str) -> str:
    """Preserve relative links while converting published Markdown targets."""
    return re.sub(
        r"\]\(([^)#]+)\.md(#[^)]+)?\)",
        lambda match: "](" + match.group(1) + ".html" + (match.group(2) or "") + ")",
        source,
    )


def convert_md(path: pathlib.Path) -> dict:
    source = rewrite_markdown_links(path.read_text(encoding="utf-8"))
    md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])
    body = md.convert(source)
    # run mermaid code fences -> <pre class="mermaid"> so the JS picks them up
    body = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        lambda m: f'<pre class="mermaid">{m.group(1)}</pre>',
        body,
        flags=re.S,
    )
    # WaveDrom reads WaveJSON from raw-text script elements. Markdown has
    # HTML-escaped the fence contents, so decode them before embedding.
    body = re.sub(
        r'<pre><code class="language-wavedrom">(.*?)</code></pre>',
        lambda m: (
            '<script type="WaveDrom">\n'
            + html.unescape(m.group(1)).replace("</script", r"<\/script")
            + "\n</script>"
        ),
        body,
        flags=re.S,
    )
    title = source.splitlines()[0].lstrip("# ").strip()
    return {"name": path.stem, "title": title, "body": body}


def validate_mermaid(paths: list[pathlib.Path], node: str) -> int:
    """Parse every Mermaid fence with Mermaid's API; return diagram count."""
    count = 0
    with tempfile.TemporaryDirectory(prefix="micronic-mermaid-") as temp_dir:
        temp = pathlib.Path(temp_dir)
        for path in paths:
            source = path.read_text(encoding="utf-8")
            for diagram_number, diagram in enumerate(
                MERMAID_FENCE_RE.findall(source), start=1
            ):
                count += 1
                input_path = temp / "diagram.mmd"
                input_path.write_text(diagram, encoding="utf-8")
                result = subprocess.run(
                    [node, str(MERMAID_VALIDATOR), str(input_path)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode:
                    detail = result.stderr.strip() or result.stdout.strip()
                    raise SystemExit(
                        f"Mermaid validation failed: {path.name} "
                        f"diagram {diagram_number}\n{detail}"
                    )
    return count


def validate_wavedrom(paths: list[pathlib.Path], wavedrom: str) -> int:
    """Parse every WaveDrom fence with WaveDrom CLI; return diagram count."""
    count = 0
    with tempfile.TemporaryDirectory(prefix="micronic-wavedrom-") as temp_dir:
        input_path = pathlib.Path(temp_dir) / "diagram.json5"
        for path in paths:
            source = path.read_text(encoding="utf-8")
            for diagram_number, diagram in enumerate(
                WAVEDROM_FENCE_RE.findall(source), start=1
            ):
                count += 1
                input_path.write_text(diagram, encoding="utf-8")
                result = subprocess.run(
                    [wavedrom, "--input", str(input_path)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode or "<svg" not in result.stdout:
                    detail = result.stderr.strip() or result.stdout.strip()
                    raise SystemExit(
                        f"WaveDrom validation failed: {path.name} "
                        f"diagram {diagram_number}\n{detail}"
                    )
    return count


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
<script src="{WAVEDROM_SKIN_JS}"></script>
<script src="{WAVEDROM_JS}"></script>
</head><body onload="WaveDrom.ProcessAll()">
<nav>{nav}</nav>
{doc["body"]}
</body></html>"""

def build_nav_items(current: pathlib.Path) -> str:
    current_dir = output_path(current).parent
    paths = {path.relative_to(ROOT).as_posix(): path
             for path in published_markdown_paths()}

    def link(path: pathlib.Path, label: str) -> str:
        href = os.path.relpath(output_path(path), current_dir).replace(os.sep, "/")
        return f'<a href="{href}">{html.escape(label)}</a>'

    groups = []
    home = paths["README.md"]
    href = os.path.relpath(output_path(home), current_dir).replace(os.sep, "/")
    groups.append(f'<a href="{href}">Home</a>')
    for title, index in NAV_GROUPS:
        index_path = paths[index]
        entries = [link(index_path, title)]
        prefix = index.rsplit("/", 1)[0] + "/"
        for key in sorted(paths):
            if key.startswith(prefix) and key != index:
                path = paths[key]
                entries.append(link(path, path.stem.replace("-", " ")))
        groups.append(
            '<span class="nav-group"><strong>'
            + html.escape(title)
            + ':</strong> '
            + " · ".join(entries)
            + "</span>"
        )
    return " | ".join(groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate-mermaid",
        action="store_true",
        help="parse every Mermaid fence with Mermaid before building",
    )
    parser.add_argument(
        "--validate-wavedrom",
        action="store_true",
        help="parse every WaveDrom fence with wavedrom before building",
    )
    args = parser.parse_args()

    markdown_paths = published_markdown_paths()
    if args.validate_mermaid:
        node = shutil.which("node")
        mermaid_package = ROOT / "node_modules" / "mermaid" / "package.json"
        if node is None:
            parser.error("--validate-mermaid requires Node.js")
        if not mermaid_package.is_file():
            parser.error(
                "--validate-mermaid requires local diagram dependencies; "
                "run 'npm install' in doc/"
            )
        count = validate_mermaid(markdown_paths, node)
        print(f"Validated {count} Mermaid diagram(s).")
    if args.validate_wavedrom:
        local_wavedrom = ROOT / "node_modules" / ".bin" / "wavedrom"
        wavedrom = (
            str(local_wavedrom)
            if local_wavedrom.is_file()
            else shutil.which("wavedrom")
        )
        if wavedrom is None:
            parser.error(
                "--validate-wavedrom requires WaveDrom CLI; "
                "run 'npm install' in doc/"
            )
        count = validate_wavedrom(markdown_paths, wavedrom)
        print(f"Validated {count} WaveDrom diagram(s).")

    OUT.mkdir(exist_ok=True)
    for md in markdown_paths:
        doc = convert_md(md)
        destination = output_path(md)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(wrap(doc, build_nav_items(md)), encoding="utf-8")
        print(f"wrote {destination}")
    print("Done. Mermaid and WaveDrom render on page open (need CDN access).")

if __name__ == "__main__":
    main()
