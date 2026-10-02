import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Omar Web3 — AI Security CTF",
  description: "Learn AI security by breaking vulnerable systems.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-4xl px-4 py-6">
          <header className="mb-8 flex items-center justify-between">
            <Link href="/" className="text-sm font-semibold tracking-widest text-accent">
              OMAR WEB3 · AI SECURITY CTF
            </Link>
            <Link href="/challenges" className="text-sm text-slate-400 hover:text-accent">
              Challenges
            </Link>
          </header>
          {children}
          <footer className="mt-16 border-t border-edge pt-6 text-xs text-slate-500">
            Local-first AI Security CTF · For educational use only.
          </footer>
        </div>
      </body>
    </html>
  );
}
