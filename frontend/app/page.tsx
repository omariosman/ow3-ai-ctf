"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPlayerId, listChallenges, type ChallengeSummary } from "@/lib/api";

export default function HomePage() {
  const [challenges, setChallenges] = useState<ChallengeSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listChallenges(getPlayerId())
      .then(setChallenges)
      .catch((e) => setError(e.message));
  }, []);

  const total = challenges?.length ?? 0;
  const points = challenges?.reduce((s, c) => s + c.points, 0) ?? 0;
  const solved = challenges?.filter((c) => c.solved).length ?? 0;

  return (
    <main>
      <section className="mb-10">
        <p className="text-xs font-semibold tracking-[0.3em] text-accent">OMAR WEB3</p>
        <h1 className="mt-2 text-4xl font-bold text-white">AI Security CTF</h1>
        <p className="mt-3 max-w-xl text-slate-400">
          Learn AI security by breaking vulnerable systems. Each challenge targets an
          architectural weakness — not a magic prompt — and is solved by a deterministic
          condition checked in code.
        </p>
        <div className="mt-6">
          <Link href="/challenges" className="btn">
            View Challenges
          </Link>
        </div>
      </section>

      {error && (
        <div className="card border-red-900 text-red-300">
          Could not reach the backend: {error}
        </div>
      )}

      <section className="grid grid-cols-3 gap-4">
        <Stat label="Challenges" value={total} />
        <Stat label="Total Points" value={points} />
        <Stat label="Solved" value={solved} />
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card text-center">
      <div className="text-3xl font-bold text-white">{value}</div>
      <div className="mt-1 text-xs uppercase tracking-wider text-slate-500">{label}</div>
    </div>
  );
}
