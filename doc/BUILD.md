# Building the documentation site (MkDocs Material)

The reader-facing documents are plain Markdown organised under the
repository-root `mkdocs.yml` nav: `manual/` (programmer-facing guides),
`reference/` (API/ABI contracts with stability terms), `protocol/`
(Commstar), and `re-notes/` (reverse-engineering evidence). The legacy
`internals/` and `manual/` URLs are preserved by `mkdocs-redirects`
(`redirect_maps` in `mkdocs.yml`); their source files have moved. Research
records live in `research/` and are published under the reverse-engineering
navigation. `doc/review.md` is a maintainer review excluded from the site.

Mermaid and WaveDrom diagrams are rendered client-side from jsDelivr.
Each diagram retains an expandable text-source fallback. If its renderer
cannot load or fails, the fallback opens with a visible status message;
with JavaScript disabled the original fenced source remains readable.

Anchor validation is enabled (`validation.links.anchors: warn`) so
`--strict` catches broken cross-page anchors — the split’s contract→evidence
links depend on it. Redirects for moved pages use `mkdocs-redirects`
(`requirements.txt`).

## Build

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
mkdocs serve       # local preview at http://127.0.0.1:8000/
mkdocs build --strict  # writes site-mkdocs/ at the repo root, fails on warnings
```

Run those commands from the repository root. From `doc/` you can use the
Makefile:

```bash
make build      # mkdocs build --strict
make check      # build, rendered HTML checks, and regression/example tests
make serve      # live preview
make clean      # rm -rf ../site-mkdocs
```

`make build` also checks the generated HTML with `analysis/check_docs.py`:
table-like paragraphs, inconsistent table column counts, relative article
links/fragments, and local script/image/stylesheet targets. It does not
validate external URLs, root-relative deployment URLs, or firmware semantics.
A strict MkDocs build alone does not catch malformed Markdown tables.

## Browser checks

Use a separate environment if you do not want browser dependencies in the
normal documentation environment:

```sh
python3 -m venv /tmp/micronic-doc-browser
/tmp/micronic-doc-browser/bin/pip install -r requirements-doc-browser.txt
/tmp/micronic-doc-browser/bin/python -m playwright install --with-deps chromium --only-shell
timeout 180s /tmp/micronic-doc-browser/bin/python analysis/check_doc_browser.py
```

Build the site first. This starts a temporary loopback HTTP server and tests
light/dark themes, a narrow viewport, diagram rendering, keyboard access to
the fallback, blocked external assets, and JavaScript-disabled reading.
Mermaid uses a real protocol page; a small fixture also exercises WaveDrom.
This is a smoke test, not a complete accessibility certification.

The GitHub workflow runs these checks on pull requests and master pushes.
Pull requests have read-only repository permissions and cannot deploy;
only master pushes or manual workflow dispatch publish the site.
