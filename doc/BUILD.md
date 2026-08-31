# Building the documentation site (MkDocs Material)

The reader-facing documents are plain Markdown organised under the
repository-root `mkdocs.yml` nav: `manual/` (programmer-facing guides),
`reference/` (API/ABI contracts with stability terms), `protocol/`
(Commstar), and `re-notes/` (reverse-engineering evidence). The legacy
`internals/` and `manual/` URLs are preserved by `mkdocs-redirects`
(`redirect_maps` in `mkdocs.yml`); their source files have moved. Research
records live in `research/` and are excluded from the published
navigation.

Mermaid and WaveDrom diagrams are rendered client-side from jsDelivr.

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
make serve      # live preview
make clean      # rm -rf ../site-mkdocs
```
