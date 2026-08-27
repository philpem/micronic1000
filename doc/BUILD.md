# Building the documentation site (Markdown → HTML)

The documents are plain Markdown. Mermaid fences (` ```mermaid ``) are
used for sequence and state-transition diagrams. WaveDrom fences
(` ```wavedrom ``) describe digital timing diagrams in WaveJSON.

## Option A — python-markdown + client-side diagrams (zero node deps)

```sh
python3 -m pip install markdown      # once
python3 doc/build.py                  # writes doc/site-html/*.html
```

Open `doc/site-html/index.html` in a browser. Mermaid and WaveDrom are
rendered client-side from jsDelivr. The Mermaid build uses an ES-module
import, so a local replacement must also be an ES module. If you must
work offline, download the Mermaid bundle plus WaveDrom's engine and
default-skin bundles to `doc/`, then point `MERMAID_JS`, `WAVEDROM_JS`,
and `WAVEDROM_SKIN_JS` at the local files in `build.py`. WaveDrom's
browser engine expects the default skin to have initialized
`window.WaveSkin`; the generated pages therefore load the skin first.

## Validate diagrams

The HTML build can ask both renderers' own parsers to check every diagram
before writing the site. This requires Mermaid CLI (`mmdc`) and WaveDrom
CLI (`wavedrom`):

```bash
npm install -g @mermaid-js/mermaid-cli@11
npm install -g wavedrom@3.6.2
cd doc
make validate
```

Equivalently, run `python3 doc/build.py --validate-mermaid
--validate-wavedrom` from the repository root. A parse failure identifies
the Markdown file and diagram number and stops the build.

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
       --to html doc/protocol-comms.md -o /tmp/protocol.html
```

## Option C — mermaid CLI for static SVG

If Node.js is available, you can pre-render each diagram to SVG with
`mmdc` (mermaid-cli) and inline the SVGs so the final HTML needs no
browser JS:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i diagram.mmd -o diagram.svg
```

A Makefile is provided as a convenience:

```bash
make html      # python-markdown build (option A)
make validate  # validate Mermaid + WaveDrom, then build HTML
make svg       # if mmdc is available: pre-render mermaid -> svg site
make clean     # remove doc/site-html
```
