"""Smoke-test built docs, diagrams, keyboard fallback, and narrow layouts."""

import argparse
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def check_browser(site):
    handler = functools.partial(QuietHandler, directory=str(site.resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    fixture = """<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/stylesheets/diagrams.css"></head><body>
<div class="mermaid">graph TD; Source--&gt;Destination;</div>
<pre class="wavedrom"><code>{"signal":[{"name":"clock","wave":"p..."}]}</code></pre>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/wavedrom@3.6.2/skins/default.js"></script>
<script src="https://cdn.jsdelivr.net/npm/wavedrom@3.6.2/wavedrom.min.js"></script>
<script src="/javascripts/diagrams.js"></script></body></html>"""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            for width, scheme in [(1280, "light"), (390, "dark")]:
                page.set_viewport_size({"width": width, "height": 900})
                page.emulate_media(color_scheme=scheme)
                for path in ["manual/first-program/", "reference/memory-map/", "protocol/commstar/"]:
                    page.goto(f"{origin}/{path}", wait_until="networkidle")
                    page.locator("article h1").wait_for()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), path
                    if path == "protocol/commstar/":
                        page.wait_for_function("document.querySelector('.diagram svg') !== null")
                        assert page.locator(".diagram [role=status]").count() == 0
                        summary = page.locator(".diagram summary").first
                        summary.focus()
                        page.keyboard.press("Space")
                        assert page.locator(".diagram details").first.get_attribute("open") is not None
            assert not errors, errors
            context.route("**/diagram-fixture.html", lambda route: route.fulfill(body=fixture, content_type="text/html"))
            page.goto(f"{origin}/diagram-fixture.html", wait_until="networkidle")
            page.wait_for_function("document.querySelectorAll('.diagram svg').length === 2")
            assert page.locator(".diagram [role=status]").count() == 0
            context.close()

            offline = browser.new_context(viewport={"width": 390, "height": 900}, color_scheme="dark")
            offline.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
            offline.route("**/diagram-fixture.html", lambda route: route.fulfill(body=fixture, content_type="text/html"))
            page = offline.new_page()
            for path in ["protocol/commstar/", "diagram-fixture.html"]:
                page.goto(f"{origin}/{path}", wait_until="networkidle")
                page.get_by_text("Diagram unavailable. Read the text source below.").first.wait_for()
                assert page.locator(".diagram details[open]").count() == page.locator(".diagram").count()
                assert page.locator(".diagram details pre").first.inner_text().strip()
            offline.close()

            no_script = browser.new_context(java_script_enabled=False)
            page = no_script.new_page()
            page.goto(f"{origin}/protocol/commstar/", wait_until="domcontentloaded")
            assert page.locator(".mermaid").first.inner_text().strip()
            no_script.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    print("Browser checks passed: light/dark, narrow layout, diagrams, keyboard, CDN failure, no JavaScript")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?", type=Path, default=Path("site-mkdocs"))
    check_browser(parser.parse_args().site)
