# Building the documentation site (Markdown → HTML)

The documents are plain Markdown. Mermaid diagrams (` ```mermaid ``
blocks) are used for sequence and state-transition diagrams because
they render natively on GitHub and in most Markdown→HTML pipelines —
a better fit than Graphviz/DOT for web output.

## Option A — python-markdown + Mermaid on CDN (zero node deps)

```sh
python3 -m pip install markdown      # once
python3 doc/build.py                  # writes doc/site-html/*.html
```

Open `doc/site-html/index.html` in a browser. Mermaid diagrams are
rendered client-side from `https://cdn.jsdelivr.net/.../mermaid.min.js`.
If you must work offline, download that JS to `doc/` and point
`MERMAID_JS` at the local file in `build.py`.

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
make svg       # if mmdc is available: pre-render mermaid -> svg site
make clean     # remove doc/site-html
```