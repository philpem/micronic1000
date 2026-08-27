/* Render custom fenced diagrams after Material has loaded the libraries. */
document.addEventListener("DOMContentLoaded", () => {
  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false });
    window.mermaid.run({ querySelector: ".mermaid" });
  }

  if (window.WaveDrom) {
    // WaveDrom consumes WaveJSON only from script[type=WaveDrom].  Keep the
    // source fence as text until this point so MkDocs can safely escape it.
    document.querySelectorAll("pre.wavedrom").forEach((fence) => {
      const source = fence.querySelector("code");
      const diagram = document.createElement("script");
      diagram.type = "WaveDrom";
      diagram.textContent = source ? source.textContent : fence.textContent;
      fence.replaceWith(diagram);
    });
    window.WaveDrom.ProcessAll();
  }
});
