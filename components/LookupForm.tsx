"use client";

import { FormEvent, useState } from "react";
import { lookupHref } from "@/lib/lookup";

const TESTS = [
  { q: "96813", label: "96813 · Honolulu" },
  { q: "90210", label: "90210 · Beverly Hills" },
  { q: "82001", label: "82001 · Cheyenne" },
];

const ISLANDS = ["Oʻahu", "Maui", "Molokaʻi", "Lānaʻi", "Kauaʻi", "Hawaiʻi Island"];

export function LookupForm({ initial = "" }: { initial?: string }) {
  const [q, setQ] = useState(initial);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    window.location.href = lookupHref(q.trim());
  }

  return (
    <form className="lookup" onSubmit={onSubmit}>
      <label htmlFor="q">ZIP, address, or island</label>
      <div className="lookup-row">
        <input
          id="q"
          name="q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="96813 or 415 S Beretania St, Honolulu, HI 96813"
          autoComplete="postal-code"
        />
        <button type="submit">Look up ballot</button>
      </div>
      <div className="chips">
        {TESTS.map((t) => (
          <a key={t.q} href={lookupHref(t.q)}>
            {t.label}
          </a>
        ))}
        {ISLANDS.map((n) => (
          <a key={n} href={lookupHref(n)}>
            {n}
          </a>
        ))}
      </div>
      <p className="muted">
        General election Tuesday, November 3, 2026. Hawaiʻi is the gold template; other states
        show FEC 2026 House/Senate filings until state databases are wired.
      </p>
    </form>
  );
}
