# Micronic 1000 doc build
# See doc/BUILD.md for full instructions.

MD       := $(shell find . \( -path './research' -o -path './node_modules' -o -path './site-html' \) -prune -o -name '*.md' -print)
OUT      := site-html

html: $(OUT)/index.html

$(OUT)/index.html: build.py $(MD)
	python3 build.py

validate: ## validate Mermaid and WaveDrom diagrams, then build HTML
	@test -d node_modules/mermaid || { echo "diagram dependencies missing; run: npm install"; exit 1; }
	python3 build.py --validate-mermaid --validate-wavedrom

svg: ## pre-render mermaid to svg (needs mmdc)
	@command -v mmdc >/dev/null 2>&1 || { echo "mmdc not found; install with: npm i -g @mermaid-js/mermaid-cli"; exit 1; }
	mkdir -p $(OUT)/svg
	@for f in $$(grep -rl '```mermaid' *.md); do \
	  echo "$$f"; done

clean:
	rm -rf $(OUT)

.PHONY: html validate svg clean
.PHONY: help
help:
	@grep -E '^[a-z]+:' Makefile
