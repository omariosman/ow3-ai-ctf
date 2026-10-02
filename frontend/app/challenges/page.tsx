"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPlayerId, listChallenges, type ChallengeSummary } from "@/lib/api";

export default function ChallengesPage() {
  const [challenges, setChallenges] = useState<ChallengeSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listChallenges(getPlayerId())
      .then(setChallenges)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <main>
      <h1 className="mb-6 text-2xl font-bold text-white">Challenges</h1>

      {error && (
        <div className="card border-red-900 text-red-300">
          Could not reach the backend: {error}
        </div>
      )}

      {!challenges && !error && <p className="text-slate-500">Loading…</p>}

      <div className="grid gap-4 sm:grid-cols-2">
        {challenges?.map((c) => (
          <div key={c.slug} className="card flex flex-col">
            <div className="flex items-start justify-between">
              <h2 className="text-lg font-semibold text-white">{c.title}</h2>
              {c.solved && (
                <span className="badge border-green-700 text-green-400">Solved</span>
              )}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="badge">{c.category}</span>
              <span className="badge capitalize">{c.difficulty}</span>
              <span className="badge">{c.points} pts</span>
            </div>
            <div className="mt-5">
              <Link href={`/challenges/${c.slug}`} className="btn">
                Start Challenge
              </Link>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
