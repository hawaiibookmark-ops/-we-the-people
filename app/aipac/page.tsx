"use client";

import { useEffect, useMemo, useState } from "react";
import { dataUrl } from "@/lib/config";

type Row = {
  name: string;
  candidate_id: string;
  office: string;
  state: string;
  district: string;
  party: string;
  cycles: number[];
  direct_total: number;
  direct_count: number;
  earmarked_total: number;
  earmarked_count: number;
  ie_support_total: number;
  ie_support_count: number;
  ie_oppose_total: number;
  ie_oppose_count: number;
  udp_direct_total: number;
  udp_direct_count: number;
  first_date: string | null;
  last_date: string | null;
  fec_url: { candidate: string; aipac_pac_disbursements: string | null; udp_independent_expenditures: string | null };
  source_url: string;
  retrieved_at: string;
};
type Doc = { generated_at: string; notes: string[]; committees: { id: string; name: string; url: string }[]; candidates: Row[] };
type SortKey = "name" | "state" | "direct_total" | "earmarked_total" | "ie_support_total" | "ie_oppose_total";

const usd = (n: number) => (n ? n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }) : "—");

export default function AipacPage() {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [err, setErr] = useState("");
  const [state, setState] = useState("");
  const [q, setQ] = useState("");
  const [id, setId] = useState("");
  const [sort, setSort] = useState<SortKey>("state");
  const [desc, setDesc] = useState(false);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    setId((p.get("id") || "").toUpperCase());
    setState((p.get("state") || "").toUpperCase());
    fetch(dataUrl("aipac/index.json"))
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setDoc)
      .catch(() => setErr("Could not load the data file."));
  }, []);

  const states = useMemo(() => Array.from(new Set((doc?.candidates || []).map((c) => c.state).filter(Boolean))).sort(), [doc]);
  const rows = useMemo(() => {
    let r = doc?.candidates || [];
    if (id) r = r.filter((c) => c.candidate_id === id);
    if (state) r = r.filter((c) => c.state === state);
    if (q) r = r.filter((c) => (c.name || "").toLowerCase().includes(q.toLowerCase()));
    const s = [...r].sort((a, b) => {
      const x = a[sort] ?? "";
      const y = b[sort] ?? "";
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return desc ? -c : c;
    });
    return s;
  }, [doc, id, state, q, sort, desc]);

  const head = (k: SortKey, label: string) => (
    <th>
      <button
        type="button"
        className="pac-toggle"
        onClick={() => {
          if (sort === k) setDesc(!desc);
          else {
            setSort(k);
            setDesc(k !== "name" && k !== "state");
          }
        }}
      >
        {label}
        {sort === k ? (desc ? " ▼" : " ▲") : ""}
      </button>
    </th>
  );

  return (
    <section className="hero">
      <p className="kicker">Money from AIPAC committees</p>
      <h1>AIPAC PAC and United Democracy Project, from their FEC filings</h1>
      <p className="lede">
        Federal candidates who received contributions from the AIPAC PAC (FEC{" "}
        <a href="https://www.fec.gov/data/committee/C00797670/">C00797670</a>), including members&apos; contributions
        it collected and passed on (earmarked), and candidates the United Democracy Project super PAC (FEC{" "}
        <a href="https://www.fec.gov/data/committee/C00799031/">C00799031</a>) spent supporting or opposing. Cycles
        2022–2026. Official FEC data only. State and local races are not covered.
      </p>
      {err && <div className="flag">{err}</div>}
      {doc && (
        <>
          <div className="lookup-row">
            <label>
              State{" "}
              <select value={state} onChange={(e) => setState(e.target.value)}>
                <option value="">All states</option>
                {states.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Name <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name" />
            </label>
            {id && (
              <button type="button" className="pac-toggle" onClick={() => setId("")}>
                Show all candidates
              </button>
            )}
          </div>
          <p className="muted">
            {rows.length.toLocaleString()} candidate{rows.length === 1 ? "" : "s"} shown. Data retrieved{" "}
            {doc.generated_at}.
          </p>
          {id && rows.length === 0 && (
            <p className="muted">No entries for FEC candidate {id} in these committees&apos; filings for 2022–2026.</p>
          )}
          <div className="council-record-table-wrap">
            <table>
              <thead>
                <tr>
                  {head("name", "Candidate (as filed)")}
                  {head("state", "Office")}
                  {head("direct_total", "Received from AIPAC PAC")}
                  {head("earmarked_total", "Received earmarked via AIPAC PAC")}
                  {head("ie_support_total", "UDP spent supporting")}
                  {head("ie_oppose_total", "UDP spent opposing")}
                  <th>Dates</th>
                  <th>FEC records</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.candidate_id}>
                    <td>
                      <strong>{c.name}</strong>
                      <div className="muted">
                        {c.party || "Party not listed"} · {c.candidate_id} · {c.cycles.join(", ")}
                      </div>
                    </td>
                    <td>
                      {c.office} {c.state}
                      {c.district && c.district !== "00" ? `-${c.district}` : ""}
                    </td>
                    <td>
                      {usd(c.direct_total)}
                      {c.direct_count ? <div className="muted">{c.direct_count} entries</div> : null}
                    </td>
                    <td>
                      {usd(c.earmarked_total)}
                      {c.earmarked_count ? <div className="muted">{c.earmarked_count} entries</div> : null}
                    </td>
                    <td>
                      {usd(c.ie_support_total)}
                      {c.ie_support_count ? <div className="muted">{c.ie_support_count} entries</div> : null}
                    </td>
                    <td>
                      {usd(c.ie_oppose_total)}
                      {c.ie_oppose_count ? <div className="muted">{c.ie_oppose_count} entries</div> : null}
                    </td>
                    <td className="muted">
                      {c.first_date || "—"}
                      {c.last_date && c.last_date !== c.first_date ? ` to ${c.last_date}` : ""}
                    </td>
                    <td>
                      <a href={c.fec_url.candidate}>Candidate</a>
                      {c.fec_url.aipac_pac_disbursements && (
                        <>
                          {" · "}
                          <a href={c.fec_url.aipac_pac_disbursements}>AIPAC PAC</a>
                        </>
                      )}
                      {c.fec_url.udp_independent_expenditures && (
                        <>
                          {" · "}
                          <a href={c.fec_url.udp_independent_expenditures}>UDP</a>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <article className="card">
            <h2>How these numbers are built</h2>
            <ul>
              {doc.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </article>
        </>
      )}
    </section>
  );
}
