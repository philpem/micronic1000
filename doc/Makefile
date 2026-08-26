# Micronic 1000 doc build
# See doc/BUILD.md for full instructions.

MD       := $(wildcard *.md)
OUT      := site-html

html: $(OUT)/index.html

$(OUT)/index.html: build.py $(MD)
	python3 build.py

svg: ## pre-render mermaid to svg (needs mmdc)
	@command -v mmdc >/dev/null 2>&1 || { echo "mmdc not found; install with: npm i -g @mermaid-js/mermaid-cli"; exit 1; }
	mkdir -p $(OUT)/svg
	@for f in $$(grep -rl '```mermaid' *.md); do \
	  echo "$$f"; done

clean:
	rm -rf $(OUT)

.PHONY: html svg clean
.PHONY: help
help:
	@grep -E '^[a-z]+:' Makefile