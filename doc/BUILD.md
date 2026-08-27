# Building the documentation site (Markdown → HTML)

The reader-facing documents are plain Markdown in the top-level index plus
`manual/`, `protocol/`, and `internals/`. Research records remain in
`research/` and are intentionally excluded from the published navigation.
Mermaid fences (` ```mermaid ``) are
used for sequence and state-transition diagrams. WaveDrom fences
(` ```wavedrom ``) describe digital timing diagrams in WaveJSON.

## Recommended site build — MkDocs Material

MkDocs Material is the supported documentation site generator. Its
configuration and dependency list are in the repository-root `mkdocs.yml` and
`requirements.txt`;
the explicit `nav` tree keeps the programmer manual, protocol specification,
and internals easy to browse while excluding the research archive. MkDocs
loads Mermaid and WaveDrom from jsDelivr: Mermaid fences render as diagrams,
and WaveDrom fences are converted from their safely escaped code fence into
the `script[type=WaveDrom]` element required by WaveDrom.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
mkdocs serve       # local preview at http://127.0.0.1:8000/
mkdocs build       # writes site-mkdocs/
```

Run those commands from the repository root. The generated site is written to
`site-mkdocs/` (also at the repository root).

The legacy `build.py` remains available for the lightweight HTML build and
diagram parser validation below.

## Option A — python-markdown + client-side diagrams (zero node deps)

```sh
python3 -m pip install markdown      # once
python3 doc/build.py                  # writes doc/site-html/*.html
```

Open `doc/site-html/index.html` in a browser. The output preserves the
source directory layout, for example
`doc/site-html/protocol/commstar.html`. Mermaid and WaveDrom are
rendered client-side from jsDelivr. The Mermaid build uses an ES-module
import, so a local replacement must also be an ES module. If you must
work offline, download the Mermaid bundle plus WaveDrom's engine and
default-skin bundles to `doc/`, then point `MERMAID_JS`, `WAVEDROM_JS`,
and `WAVEDROM_SKIN_JS` at the local files in `build.py`. WaveDrom's
browser engine expects the default skin to have initialized
`window.WaveSkin`; the generated pages therefore load the skin first.

## Validate diagrams

The HTML build can ask both renderers' own parsers to check every diagram
before writing the site. With Node.js 20 or newer, install the pinned local
dependencies once:

```bash
cd doc
npm install
make validate
```

Equivalently, run `python3 doc/build.py --validate-mermaid
--validate-wavedrom` from the repository root. A parse failure identifies
the Markdown file and diagram number and stops the build.

Validation calls Mermaid's `parse()` API directly and WaveDrom's
browser-free CLI. It does **not** install Mermaid CLI (`mmdc`), Puppeteer,
Chrome, or `chrome-headless-shell`. A browser is only needed for the
optional static-SVG workflow below.

A timing diagram is a `wavedrom` fence containing WaveJSON:

````markdown
```wavedrom
{ signal: [
  { name: 'input', wave: '0.1..0.' }
]}
```
````

## Option B — pandoc (if installed)

```bash
pandoc --standalone --embed-resources \
       --from markdown+pipe_tables+fenced_code_attributes \
       --to html doc/protocol/commstar.md -o /tmp/commstar.html
```

## Option C — mermaid CLI for static SVG

If Node.js is available, you can pre-render each diagram to SVG with
`mmdc` (mermaid-cli) and inline the SVGs so the final HTML needs no
browser JS. Unlike syntax validation, `mmdc` renders through Puppeteer
and therefore needs a compatible Chrome/Chromium executable:

```bash
npm install -g @mermaid-js/mermaid-cli@11
mmdc -i diagram.mmd -o diagram.svg
```

A Makefile is provided as a convenience:

```bash
make html      # python-markdown build (option A)
make validate  # validate Mermaid + WaveDrom, then build HTML
make svg       # if mmdc is available: pre-render mermaid -> svg site
make clean     # remove doc/site-html
```
