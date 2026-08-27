"use client";

import { useEffect, useMemo, useState } from "react";
import { LookupForm } from "@/components/LookupForm";
import { ResultsView } from "@/components/ResultsView";
import { loadBundle, parseQuery, runLookup, type LookupResult } from "@/lib/lookup";

export default function LookupPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"load" | "ready" | "error">("load");
  const [result, setResult] = useState<LookupResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setQ(params.get("q") || "");
  }, []);

  const parsed = useMemo(() => (q ? parseQuery(q) : null), [q]);

  useEffect(() => {
    if (!parsed) {
      setStatus("ready");
      setResult(null);
      return;
    }
    let cancelled = false;
    setStatus("load");
    loadBundle()
      .then((bundle) => {
        if (cancelled) return;
        setResult(runLookup(bundle, parsed));
        setStatus("ready");
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [parsed]);

  return (
    <section className="hero">
      <p className="kicker">Ballot lookup</p>
      <h1>{q ? `Results for ${q}` : "Look up your district"}</h1>
      <LookupForm initial={q} />
      {status === "load" && q && <p className="muted">Loading official extracts…</p>}
      {status === "error" && <p className="flag">{error}</p>}
      {result && <ResultsView result={result} />}
    </section>
  );
}
