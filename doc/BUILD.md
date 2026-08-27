# Building the documentation site (MkDocs Material)

The reader-facing documents are plain Markdown organised under the
repository-root `mkdocs.yml` nav: `manual/` (programmer-facing API),
`protocol/` (Commstar), and `internals/` (OS/hardware). Research records
live in `research/` and are excluded from the published navigation.

Mermaid and WaveDrom diagrams are rendered client-side from jsDelivr.

## Build

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
mkdocs serve       # local preview at http://127.0.0.1:8000/
mkdocs build       # writes site-mkdocs/ at the repo root
```

Run those commands from the repository root. From `doc/` you can use the
Makefile:

```bash
make build      # mkdocs build
make serve      # live preview
make clean      # rm -rf ../site-mkdocs
```
