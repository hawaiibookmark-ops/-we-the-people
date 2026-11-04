"use client";

import { useEffect, useMemo, useState } from "react";
import { dataUrl } from "@/lib/config";
import type { ResultContest, ResultsIndex, ResultsState } from "@/lib/results";

const OFFICE_LABEL: Record<string, string> = {
  "US Senate": "U.S. Senate",
  Governor: "Governor",
  "US House": "U.S. House",
  "Ballot Measure": "Statewide ballot measures",
  "Ballot Measure (statewide)": "Statewide ballot measures",
  "State Senate": "State Senate",
  "State House": "State House",
  "OHA Trustee": "Office of Hawaiian Affairs",
  "County Mayor": "County mayor",
  "County Council": "County council",
  "Ballot Measure (county)": "County ballot measures",
};
const OFFICE_ORDER = Object.keys(OFFICE_LABEL);
const PAGE = 40;

const n = (v: number) => v.toLocaleString("en-US");

function when(iso?: string | null): string {
  if (!iso) return "not stated by source";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", { timeZone: "Pacific/Honolulu", dateStyle: "medium", timeStyle: "short" }) + " HST";
}

function ContestCard({ c }: { c: ResultContest }) {
  const rep = c.reporting;
  const repText =
    rep && rep.reporting != null
      ? rep.total
        ? `${rep.reporting} of ${rep.total} ${rep.unit} reporting`
        : `${rep.reporting} ${rep.unit}`
      : null;
  const top = c.candidates[0]?.votes || 0;
  return (
    <article className="card result-card">
      <h3>{c.title}</h3>
      <p className="muted result-meta">
        {c.jurisdiction && c.jurisdiction !== "Statewide" ? `${c.jurisdiction} · ` : ""}
        {n(c.total_votes)} votes for listed choices
        {repText ? ` · ${repText}` : ""}
        {c.vote_for && c.vote_for > 1 ? ` · vote for ${c.vote_for}` : ""}
      </p>
      <ul className="result-list">
        {c.candidates.map((x) => {
          const lead = c.leading && x.name === c.leading;
          return (
            <li key={x.name} className={lead ? "result-row lead" : "result-row"}>
              <div className="result-line">
                <span className="result-name">
                  {x.name}
                  {x.party ? <small> {x.party}</small> : null}
                  {x.incumbent ? <span className="tag">Incumbent</span> : null}
                  {lead ? <span className="tag lead-tag">Leading</span> : null}
                </span>
                <span className="result-num">
                  {n(x.votes)}
                  {x.pct != null ? <small> {x.pct.toFixed(2)}%</small> : null}
                </span>
              </div>
              <div className="bar">
                <span style={{ width: `${top ? Math.max(1, (x.votes / top) * 100) : 0}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="muted result-meta">
        {c.margin_votes != null ? `Margin between top two: ${n(c.margin_votes)} votes (${c.margin_pct?.toFixed(2)} points). ` : ""}
        {c.notes ? `${c.notes} ` : ""}
        <strong>{c.status}.</strong> Retrieved {when(c.retrieved_at)}
        {c.results_as_of ? ` · source as of ${when(c.results_as_of)}` : ""} ·{" "}
        <a href={c.source_url} target="_blank" rel="noreferrer">
          official source
        </a>
      </p>
    </article>
  );
}

export default function ResultsPage() {
  const [index, setIndex] = useState<ResultsIndex | null>(null);
  const [code, setCode] = useState<string>("");
  const [st, setSt] = useState<ResultsState | null>(null);
  const [err, setErr] = useState("");
  const [office, setOffice] = useState("all");
  const [shown, setShown] = useState(PAGE);

  useEffect(() => {
    fetch(dataUrl("results/index.json"))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j: ResultsIndex) => {
        setIndex(j);
        const q = new URLSearchParams(window.location.search).get("state");
        const want = (q || "").toUpperCase();
        setCode(j.states.find((s) => s.state === want) ? want : "HI");
      })
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    if (!code) return;
    setSt(null);
    setOffice("all");
    setShown(PAGE);
    fetch(dataUrl(`results/${code.toLowerCase()}/index.json`))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setSt)
      .catch((e) => setErr(String(e)));
  }, [code]);

  function pick(c: string) {
    setCode(c);
    const u = new URL(window.location.href);
    u.searchParams.set("state", c.toLowerCase());
    window.history.replaceState(null, "", u.toString());
  }

  const offices = useMemo(() => {
    const set = new Set((st?.contests || []).map((c) => c.office));
    return OFFICE_ORDER.filter((o) => set.has(o)).concat([...set].filter((o) => !OFFICE_ORDER.includes(o)));
  }, [st]);

  const list = useMemo(
    () => (st?.contests || []).filter((c) => office === "all" || c.office === office),
    [st, office],
  );

  return (
    <section className="hero">
      <p className="kicker">Election Results · November 3, 2026</p>
      <h1>Results from each state&apos;s official election office.</h1>
      <p className="lede">
        Every count below is <strong>unofficial and not yet certified</strong>. Numbers change as
        counties finish counting and states canvass. We copy them from the state election office
        feeds, label each with its source and retrieval time, and never use news outlets or wire
        services. &ldquo;Leading&rdquo; means the highest count in the source when we retrieved it. It
        is not a race call.
      </p>
      {err ? <p className="flag"><strong>Could not load</strong>{err}</p> : null}
      {index ? (
        <>
          <p className="muted">
            {index.counts.states_with_results} states with official-source results loaded ·{" "}
            {index.counts.states_pending} marked &ldquo;results pending from official source&rdquo; with a link to
            the state site · data built {when(index.generated_at)}
          </p>
          <div className="state-chips" role="tablist" aria-label="Choose a state">
            {index.states.map((s) => (
              <button
                key={s.state}
                type="button"
                className={`state-chip ${s.state === code ? "on" : ""} ${s.results_status === "pending" ? "pend" : ""}`}
                onClick={() => pick(s.state)}
                title={`${s.name}: ${s.results_status === "pending" ? "results pending from official source" : s.status}`}
              >
                {s.state}
              </button>
            ))}
          </div>
          <details className="council-reading">
            <summary>How to read these numbers</summary>
            <ul className="muted">
              {index.rules.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </details>
        </>
      ) : null}

      {st ? (
        <div className="result-state">
          <h2>{st.name}</h2>
          {st.results_status === "pending" ? (
            <div className="flag">
              <strong>Results pending from official source</strong>
              <p>{st.pending_reason}</p>
              {st.source_url ? (
                <p>
                  Official results:{" "}
                  <a href={st.source_url} target="_blank" rel="noreferrer">
                    {st.source_url}
                  </a>
                </p>
              ) : null}
              <p className="muted">Checked {when(st.retrieved_at)}. We will load this state when its official feed can be read.</p>
            </div>
          ) : (
            <>
              <p className="muted">
                <strong>{st.status}.</strong> Retrieved {when(st.retrieved_at)}
                {st.results_as_of ? ` · source as of ${when(st.results_as_of)}` : ""} ·{" "}
                <a href={st.source_url || "#"} target="_blank" rel="noreferrer">
                  official source
                </a>
                {st.official_pdfs
                  ? Object.entries(st.official_pdfs).map(([k, v]) => (
                      <span key={k}>
                        {" · "}
                        <a href={v} target="_blank" rel="noreferrer">
                          {k} PDF
                        </a>
                      </span>
                    ))
                  : null}
              </p>
              {st.notes ? <p className="muted">{st.notes}</p> : null}
              <div className="chips">
                <button type="button" className={`chip ${office === "all" ? "on" : ""}`} onClick={() => { setOffice("all"); setShown(PAGE); }}>
                  All ({st.contests.length})
                </button>
                {offices.map((o) => (
                  <button key={o} type="button" className={`chip ${office === o ? "on" : ""}`} onClick={() => { setOffice(o); setShown(PAGE); }}>
                    {OFFICE_LABEL[o] || o} ({st.contests.filter((c) => c.office === o).length})
                  </button>
                ))}
              </div>
              {list.slice(0, shown).map((c) => (
                <ContestCard key={c.id} c={c} />
              ))}
              {list.length > shown ? (
                <p>
                  <button type="button" className="btn" onClick={() => setShown(shown + PAGE)}>
                    Show more ({list.length - shown} left)
                  </button>
                </p>
              ) : null}
            </>
          )}
        </div>
      ) : index ? (
        <p className="muted">Loading {code}…</p>
      ) : null}
    </section>
  );
}
