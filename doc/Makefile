# Micronic 1000 documentation build — MkDocs only.
# Run from doc/ (targets `cd ..` to reach the repo-root mkdocs.yml).
# See doc/BUILD.md.

MKDOCS ?= mkdocs

# mkdocs-redirects pulls in an upstream notice that prints on every build and
# would bury real warnings in CI logs.
export DISABLE_MKDOCS_2_WARNING = true

build: ## build the site into ../site-mkdocs
	cd .. && $(MKDOCS) build --strict

serve: ## live preview at http://127.0.0.1:8000/
	cd .. && $(MKDOCS) serve

clean: ## remove the generated site
	rm -rf ../site-mkdocs

.PHONY: build serve clean
help:
	@grep -E '^[a-z-]+:' Makefile
