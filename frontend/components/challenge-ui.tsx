"use client";

// Shared challenge-page building blocks (status pill, hint accordion).

import { useState } from "react";
import type { ChallengeDetail } from "@/lib/api";

export function StatusPill({ solved }: { solved: boolean }) {
  return (
    <span
      className={`badge ${
        solved ? "border-green-700 text-green-400" : "border-edge text-slate-400"
      }`}
    >
      Status: {solved ? "Solved" : "Not Solved"}
    </span>
  );
}

export function Hints({ hints }: { hints: ChallengeDetail["hints"] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section className="card">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
        Hints
      </h2>
      <div className="space-y-2">
        {hints.map((h) => (
          <div key={h.order} className="rounded-lg border border-edge">
            <button
              className="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
              onClick={() => setOpen(open === h.order ? null : h.order)}
            >
              <span className="text-slate-300">
                Hint {h.order} {h.cost > 0 ? `— costs ${h.cost} pts` : "— free"}
              </span>
              <span className="text-slate-500">{open === h.order ? "−" : "+"}</span>
            </button>
            {open === h.order && (
              <p className="border-t border-edge px-3 py-2 text-sm text-slate-400">
                {h.text}
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
