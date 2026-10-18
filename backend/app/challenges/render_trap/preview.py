"""Document for the isolated RenderTrap preview frame.

THE INTENTIONAL VULNERABILITY LIVES HERE: the assistant output is concatenated
into an HTML document as trusted markup, with no escaping or sanitizing. That is
exactly the bug RenderTrap teaches.

Containment (the frame is the only place this document is ever used):
* The frontend loads it with ``sandbox="allow-scripts"`` and *no*
  ``allow-same-origin``, so the frame has an opaque origin: no parent DOM,
  cookies, localStorage, or platform API access. No top-navigation, popups,
  downloads, forms, or pointer lock are granted.
* A CSP inside the document blocks every network fetch (``default-src 'none'``,
  ``connect-src 'none'``), external scripts, frames, forms and base-URI changes.
  Inline script is allowed - that is what makes the sink exploitable.
* The only thing the frame can do toward the platform is the narrow
  ``postMessage`` below, which the parent validates and the backend re-validates.

The document never contains the flag.
"""

from __future__ import annotations

import json

EVENT_TYPE = "render_execution_confirmed"

CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; "
    "base-uri 'none'"
)

# Preview runtime. ``rtPreview.confirm()`` is the "widget API" the dashboard
# exposes to rich summaries. It only shows a marker and posts one fixed-shape
# message; it takes no arguments and exposes nothing else.
_RUNTIME = """
(function () {
  var cfg = %(cfg)s;
  var sent = false;
  window.rtPreview = Object.freeze({
    confirm: function () {
      var m = document.getElementById("rt-marker");
      if (m) { m.hidden = false; }
      if (sent) { return; }
      sent = true;
      parent.postMessage({
        type: cfg.type, generation: cfg.generation, nonce: cfg.nonce
      }, "*");
    }
  });
})();
"""

_STYLE = (
    "body{font:14px/1.5 system-ui,sans-serif;margin:12px;color:#e2e8f0;"
    "background:#0b1220}h3{margin:0 0 8px;font-size:16px}p{margin:4px 0}"
    "#rt-marker{margin-top:12px;padding:6px 10px;border:1px solid #16a34a;"
    "color:#4ade80;border-radius:6px}"
)


def build_preview_document(output: str, *, generation: int, nonce: str) -> str:
    """Build the srcdoc for the sandboxed preview. ``output`` is NOT escaped."""
    cfg = json.dumps({"type": EVENT_TYPE, "generation": generation, "nonce": nonce})
    runtime = _RUNTIME % {"cfg": cfg}
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<meta http-equiv=\"Content-Security-Policy\" content=\"{CSP}\">"
        f"<style>{_STYLE}</style></head><body>"
        f"<script>{runtime}</script>"
        f"<div id=\"rt-output\">{output}</div>"  # <-- the unsafe sink
        "<div id=\"rt-marker\" hidden>Script executed in isolated preview.</div>"
        "</body></html>"
    )
