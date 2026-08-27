#!/usr/bin/env python3
"""build.py - render the Micronic-1000 doc Markdown into a single HTML
site, including Mermaid and WaveDrom diagram rendering.

Strategy: convert each .md to an HTML fragment with python-markdown,
wrap in a shared template, and load Mermaid.js and WaveDrom from CDNs
so diagrams render client-side (view the HTML in a browser).

Dependencies:  python3 -m pip install markdown
Works offline for text; diagrams require browser + net to fetch their
renderers (or locally vendored JavaScript bundles).
"""
import argparse
import html
import pathlib
import re
import shutil
import subprocess
import tempfile

import markdown

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "site-html"
MERMAID_JS = (
    "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
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
  svg{max-width:100%;height:auto}
"""

def convert_md(path: pathlib.Path) -> dict:
    source = path.read_text(encoding="utf-8")
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


def validate_mermaid(paths: list[pathlib.Path], mmdc: str) -> int:
    """Parse every Mermaid fence with Mermaid CLI; return diagram count."""
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
                output_path = temp / "diagram.svg"
                input_path.write_text(diagram, encoding="utf-8")
                result = subprocess.run(
                    [
                        mmdc,
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--quiet",
                    ],
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

def build_nav_items() -> str:
    links = []
    for f in sorted(ROOT.glob("*.md")):
        fn = "index.html" if f.stem == "README" else f"{f.stem}.html"
        label = f.stem if f.stem != "README" else "index"
        links.append(f'<a href="{fn}">{label}</a>')
    return " | ".join(links)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate-mermaid",
        action="store_true",
        help="parse every Mermaid fence with mmdc before building",
    )
    parser.add_argument(
        "--validate-wavedrom",
        action="store_true",
        help="parse every WaveDrom fence with wavedrom before building",
    )
    args = parser.parse_args()

    markdown_paths = sorted(ROOT.glob("*.md"))
    if args.validate_mermaid:
        mmdc = shutil.which("mmdc")
        if mmdc is None:
            parser.error(
                "--validate-mermaid requires Mermaid CLI (mmdc); "
                "install @mermaid-js/mermaid-cli@11"
            )
        count = validate_mermaid(markdown_paths, mmdc)
        print(f"Validated {count} Mermaid diagram(s).")
    if args.validate_wavedrom:
        wavedrom = shutil.which("wavedrom")
        if wavedrom is None:
            parser.error(
                "--validate-wavedrom requires WaveDrom CLI; "
                "install wavedrom@3.6.2"
            )
        count = validate_wavedrom(markdown_paths, wavedrom)
        print(f"Validated {count} WaveDrom diagram(s).")

    OUT.mkdir(exist_ok=True)
    nav = build_nav_items()
    for md in markdown_paths:
        doc = convert_md(md)
        fn = "index.html" if md.stem == "README" else f"{md.stem}.html"
        (OUT / fn).write_text(wrap(doc, nav), encoding="utf-8")
        print(f"wrote {OUT / fn}")
    print("Done. Mermaid and WaveDrom render on page open (need CDN access).")

if __name__ == "__main__":
    main()
