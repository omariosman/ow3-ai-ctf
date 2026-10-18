"use client";

// RenderTrap preview frame.
//
// The assistant output is intentionally interpreted as HTML, but ONLY inside
// this sandboxed iframe. The sandbox grants scripts and nothing else (no
// same-origin grant, no top-navigation, popups, downloads or forms), so the
// frame has an opaque origin and cannot reach this page, its cookies, storage
// or the platform API. The document itself also carries a CSP that blocks all
// network access. This component is challenge-specific; do not reuse it.
//
// The parent accepts exactly one message shape, and only from this iframe's
// window. It is not a general bridge: nothing in the frame can call parent code.

import { useEffect, useRef, useState } from "react";

const EVENT_TYPE = "render_execution_confirmed";

export interface ProofEvent {
  generation: number;
  nonce: string;
}

function parseProof(data: unknown): ProofEvent | null {
  if (typeof data !== "object" || data === null || Array.isArray(data)) return null;
  const keys = Object.keys(data).sort().join(",");
  if (keys !== "generation,nonce,type") return null;
  const d = data as Record<string, unknown>;
  if (d.type !== EVENT_TYPE) return null;
  if (typeof d.generation !== "number" || !Number.isInteger(d.generation)) return null;
  if (typeof d.nonce !== "string" || d.nonce.length === 0 || d.nonce.length > 64) return null;
  return { generation: d.generation, nonce: d.nonce };
}

export function RenderTrapPreview({
  html,
  generation,
  onProof,
}: {
  html: string | null;
  generation: number;
  onProof: (event: ProofEvent) => void;
}) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
  }, [html]);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      // Only the current preview frame may speak.
      if (!frameRef.current || event.source !== frameRef.current.contentWindow) return;
      const proof = parseProof(event.data);
      // Drop events from a frame that is no longer the current generation.
      if (!proof || proof.generation !== generation) return;
      onProof(proof);
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [generation, onProof]);

  if (!html) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-edge bg-ink text-sm text-slate-500">
        Generate a summary to see the preview.
      </div>
    );
  }

  return (
    <div className="relative isolate h-64 overflow-hidden rounded-lg border border-edge bg-ink">
      {!loaded && (
        <p className="absolute left-3 top-3 text-xs text-slate-500" role="status">
          Loading preview…
        </p>
      )}
      <iframe
        key={generation}
        ref={frameRef}
        title="Assistant summary preview (sandboxed)"
        sandbox="allow-scripts"
        referrerPolicy="no-referrer"
        srcDoc={html}
        onLoad={() => setLoaded(true)}
        className="h-full w-full border-0"
      />
    </div>
  );
}
