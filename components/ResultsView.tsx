import type { ReactNode } from "react";
import type { LookupResult } from "@/lib/lookup";
import type { PacQuery } from "@/lib/pacMatch";
import { CouncilRecord } from "@/components/CouncilRecord";
import { PacPanels } from "@/components/PacMoneyPanel";

function money(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function ResultsView({ result }: { result: LookupResult }) {
  const queries: (PacQuery | null)[] = [];
  for (const race of result.races) {
    for (const candidate of race.candidates) queries.push(candidate.pac || null);
  }
  return (
    <PacPanels
      queries={queries}
      render={(panelAt) => <ResultsBody result={result} panelAt={panelAt} />}
    />
  );
}

function ResultsBody({
  result,
  panelAt,
}: {
  result: LookupResult;
  panelAt: (index: number) => ReactNode;
}) {
  const { place, flags, races } = result;
  let slot = 0;
  return (
    <div>
      <div className="place">
        {place.zip && (
          <div>
            <small>ZIP (Census ZCTA)</small>
            <span>{place.zip}</span>
          </div>
        )}
        {place.stateName && (
          <div>
            <small>State</small>
            <span>{place.stateName}</span>
          </div>
        )}
        {place.island && (
          <div>
            <small>Island</small>
            <span>{place.island}</span>
          </div>
        )}
        {place.county && (
          <div>
            <small>County</small>
            <span>{place.county}</span>
          </div>
        )}
        {place.cds.map((cd) => (
          <div key={cd.district}>
            <small>U.S. House</small>
            <span>
              {place.state}-{cd.district === "00" ? "At Large" : cd.district}
            </span>
          </div>
        ))}
        {place.sldu && (
          <div>
            <small>State Senate</small>
            <span>{place.sldu.name || `District ${Number(place.sldu.district)}`}</span>
          </div>
        )}
        {place.sldl && (
          <div>
            <small>State House</small>
            <span>{place.sldl.name || `District ${Number(place.sldl.district)}`}</span>
          </div>
        )}
      </div>

      {flags.map((f) => (
        <div className="flag" key={f.title}>
          <strong>Flag · sources differ or overlap</strong>
          {f.title}. {f.detail}
        </div>
      ))}

      {result.stateFilingsNote && (
        <div className="flag">
          <strong>State filings</strong>
          {result.stateFilingsNote}
        </div>
      )}

      {races.map((race) => (
        <section className="race card" key={race.title}>
          <h2>{race.title}</h2>
          {race.emptyNote && <p className="muted">{race.emptyNote}</p>}
          {race.candidates.map((c, i) => (
            <article className="cand" key={`${c.name}-${i}`}>
              <div className="cand-head">
                <div>
                  <strong>{c.name}</strong>
                  <div className="muted">
                    {c.party || "Party as listed on source"}
                    {c.incumbent ? " · Incumbent (FEC / Clerk)" : ""}
                    {c.list === "general_only" && c.primaryVotes == null
                      ? " · Not on the primary ballot"
                      : c.primaryVotes != null
                        ? ` · Certified primary votes: ${c.primaryVotes.toLocaleString()}`
                        : ""}
                  </div>
                  {c.olvrStatus ? (
                    <p className="olvr">
                      {c.olvrStatus}
                      {c.olvrStatusSourceUrl ? (
                        <>
                          {" "}
                          <a href={c.olvrStatusSourceUrl} rel="noreferrer">
                            Source: OLVR
                          </a>
                        </>
                      ) : null}
                    </p>
                  ) : null}
                </div>
                <span className="tag">
                  {c.list === "general_nominee"
                    ? "OE party nominee"
                    : c.list === "certified_primary"
                      ? "Certified primary"
                      : c.list === "general_only"
                        ? "General only"
                        : "FEC filing"}
                </span>
              </div>
              {c.showRollCalls !== false && (
              <div className="votes">
                <p className="src">
                  Votes
                  {c.votes.itemCountAll != null
                    ? ` · ${c.votes.itemCountAll.toLocaleString()} official named roll${c.votes.itemCountAll === 1 ? "" : "s"}`
                    : ""}
                  {c.votes.status === "ok" &&
                  c.votes.itemCountAll != null &&
                  c.votes.itemCountAll > c.votes.items.length
                    ? ` · latest ${c.votes.items.length} shown`
                    : ""}
                </p>
                {c.votes.status === "ok" && c.votes.items.length > 0 ? (
                  <ul className="donor-list">
                    {c.votes.items.map((v, vi) => (
                      <li key={`${v.measure || ""}-${v.date || ""}-${vi}`}>
                        {v.sourceUrl ? (
                          <a href={v.sourceUrl} rel="noreferrer">
                            {v.measure || "Official roll"}
                          </a>
                        ) : (
                          v.measure || "Official roll"
                        )}
                        {v.voteCast ? ` · ${v.voteCast}` : ""}
                        {v.date ? ` · ${v.date}` : ""}
                        {v.question ? ` · ${v.question}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="src">{c.votes.reason}</p>
                )}
                <p className="src">
                  {c.voteLinks && c.voteLinks.length > 0 && (
                    <>
                      {c.voteLinks.map((v, vi) => (
                        <span key={v.url}>
                          {vi > 0 ? " · " : ""}
                          <a href={v.url} rel="noreferrer">
                            {v.label}
                          </a>
                        </span>
                      ))}
                      {" · "}
                    </>
                  )}
                  <a href={c.votes.sourceUrl} rel="noreferrer">
                    Source
                  </a>
                  {c.votes.retrievedAt ? ` · retrieved ${c.votes.retrievedAt}` : ""}
                  {" · Official text only. Votes are not invented. No scores."}
                </p>
              </div>
              )}
              <div className="donors">
                <p className="src">
                  Donors
                  {c.donors.itemCountAll != null
                    ? ` · ${c.donors.itemCountAll.toLocaleString()} official ${
                        c.fecId ? "Schedule A $200+" : "CSC"
                      } row${c.donors.itemCountAll === 1 ? "" : "s"}`
                    : ""}
                  {c.donors.status === "ok" &&
                  c.donors.itemCountAll != null &&
                  c.donors.itemCountAll > c.donors.items.length
                    ? ` · top ${c.donors.items.length} by amount`
                    : ""}
                </p>
                {c.donors.status === "ok" && c.donors.items.length > 0 ? (
                  <ul className="donor-list">
                    {c.donors.items.map((d, di) => (
                      <li key={`${d.name}-${d.date || ""}-${di}`}>
                        {d.fecUrl ? (
                          <a href={d.fecUrl} rel="noreferrer">
                            {d.name}
                          </a>
                        ) : (
                          d.name
                        )}{" "}
                        {money(d.amount)}
                        {d.date ? ` · ${d.date}` : ""}
                        {d.city || d.state ? ` · ${[d.city, d.state].filter(Boolean).join(", ")}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="src">{c.donors.reason}</p>
                )}
                <p className="src">
                  <a href={c.donors.sourceUrl} rel="noreferrer">
                    Source
                  </a>
                  {c.donors.retrievedAt ? ` · retrieved ${c.donors.retrievedAt}` : ""}
                  {" · Official names only. Donor lists are not sold."}
                </p>
              </div>
              {panelAt(slot++)}
              {c.councilOffice ? <CouncilRecord office={c.councilOffice} name={c.name} /> : null}
              <p className="src">
                {c.sources.map((s, si) => (
                  <span key={s.url + si}>
                    {si > 0 ? " · " : ""}
                    {s.label}{" "}
                    <a href={s.url} rel="noreferrer">
                      {s.url}
                    </a>{" "}
                    retrieved {s.retrieved_at}
                  </span>
                ))}
              </p>
            </article>
          ))}
          {race.pastResults && race.pastResults.items.length > 0 && (
            <div className="past-results">
              <h3>Past official results for this seat</h3>
              {race.pastResults.note ? <p className="src">{race.pastResults.note}</p> : null}
              {race.pastResults.items.map((item, ii) =>
                item.kind === "note" ? (
                  <p className="src" key={`note-${item.year}-${item.type}-${ii}`}>
                    {item.text}
                    {item.sourceUrl ? (
                      <>
                        {" "}
                        <a href={item.sourceUrl} rel="noreferrer">
                          Source (PDF p.{item.pdfPage})
                        </a>
                      </>
                    ) : null}
                  </p>
                ) : (
                  <div key={`${item.year}-${item.type}-${ii}`}>
                    <table>
                      <caption>
                        {item.year} {item.type}
                      </caption>
                      <thead>
                        <tr>
                          <th>Ballot name</th>
                          <th>Votes</th>
                          <th>pct_in_source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {item.rows.map((row, ri) => (
                          <tr key={`${row.ballotName}-${ri}`}>
                            <td>{row.ballotName}</td>
                            <td>{row.votes.toLocaleString()}</td>
                            <td>{row.pctInSource}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {item.sourceUrl ? (
                      <p className="src">
                        <a href={item.sourceUrl} rel="noreferrer">
                          Source (PDF p.{item.pdfPage})
                        </a>
                      </p>
                    ) : null}
                  </div>
                ),
              )}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
