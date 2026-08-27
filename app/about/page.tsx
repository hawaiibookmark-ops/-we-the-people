"use client";

import { useEffect, useState } from "react";
import { loadBundle } from "@/lib/lookup";

export default function AboutPage() {
  const [sources, setSources] = useState<{ url: string; retrieved_at: string; note?: string }[]>([]);
  const [generated, setGenerated] = useState<string>("");

  useEffect(() => {
    loadBundle()
      .then((b) => {
        setSources(b.meta.sources);
        setGenerated(b.meta.generated_at);
      })
      .catch(() => undefined);
  }, []);

  return (
    <section className="hero">
      <p className="kicker">About this hub</p>
      <h1>Official sources, timestamps, no scorecards.</h1>
      <p className="lede">
        We The People is a nonpartisan voter hub. It is not a campaign site. It does not publish
        candidate ads, issue scores, or donor lists for sale. Lookups do not require an account.
      </p>
      <article className="card">
        <h2>What is in a fact</h2>
        <p>
          Each displayed fact is tied to a source URL and a <code>retrieved_at</code> timestamp.
          Hawaiʻi November 3, 2026 nominees come from the Office of Elections certified 2026
          primary summary. Federal finance and out-of-state House/Senate names come from the FEC.
          District geography comes from Census ZCTA relationship files and the Census Geocoder.
          Incumbent vote <em>links</em> go to Congress.gov and the House Clerk — roll calls are
          not copied or invented here.
        </p>
        <p>
          If Census says a ZIP overlaps two congressional districts, both are shown. If FEC
          filings and the Hawaiʻi certified primary disagree on who is a November nominee, both
          lists are shown and flagged.
        </p>
        <p>
          Without <code>FEC_API_KEY</code>, federal Schedule A $200+ donor names stay empty and
          the FEC search is linked instead. Hawaiʻi state donors are linked to the Campaign
          Spending Commission public filing system.
        </p>
      </article>
      <article className="card" style={{ marginTop: 16 }}>
        <h2>Sources in this build</h2>
        <p className="muted">Extract generated {generated || "…"}</p>
        <ul>
          {sources.map((s) => (
            <li key={s.url}>
              <a href={s.url} rel="noreferrer">
                {s.url}
              </a>
              <div className="src">
                retrieved {s.retrieved_at}
                {s.note ? ` — ${s.note}` : ""}
              </div>
            </li>
          ))}
        </ul>
      </article>
    </section>
  );
}
