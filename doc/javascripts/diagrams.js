document.addEventListener("DOMContentLoaded", async () => {
  const diagrams = [];
  document.querySelectorAll(".mermaid, pre.wavedrom").forEach((fence) => {
    const source = fence.querySelector("code") || fence;
    const figure = document.createElement("figure");
    const status = document.createElement("p");
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const fallback = document.createElement("pre");
    figure.className = "diagram";
    status.setAttribute("role", "status");
    status.textContent = "Rendering diagram…";
    summary.textContent = "Diagram source (text fallback)";
    fallback.textContent = source.textContent;
    details.append(summary, fallback);
    fence.replaceWith(figure);
    figure.append(status, fence, details);
    diagrams.push({ fence, figure, status, details, source: source.textContent });
  });

  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
  }

  for (const diagram of diagrams) {
    try {
      if (diagram.fence.classList.contains("mermaid")) {
        if (!window.mermaid) throw new Error("Mermaid unavailable");
        await window.mermaid.run({ nodes: [diagram.fence], suppressErrors: false });
        if (!diagram.fence.querySelector("svg")) throw new Error("No rendered diagram");
      } else {
        if (!window.WaveDrom) throw new Error("WaveDrom unavailable");
        const script = document.createElement("script");
        script.type = "WaveDrom";
        script.textContent = diagram.source;
        diagram.fence.replaceWith(script);
        diagram.fence = script;
        window.WaveDrom.ProcessAll();
        if (!diagram.figure.querySelector("svg")) throw new Error("No rendered diagram");
      }
      diagram.status.remove();
    } catch (error) {
      diagram.fence.hidden = true;
      diagram.details.open = true;
      diagram.status.textContent = "Diagram unavailable. Read the text source below.";
    }
  }
});
