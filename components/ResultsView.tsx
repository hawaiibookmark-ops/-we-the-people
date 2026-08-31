import type { LookupResult } from "@/lib/lookup";

function money(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function ResultsView({ result }: { result: LookupResult }) {
  const { place, flags, races } = result;
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
                    {c.primaryVotes != null ? ` · Certified primary votes: ${c.primaryVotes.toLocaleString()}` : ""}
                  </div>
                </div>
                <span className="tag">
                  {c.list === "general_nominee"
                    ? "OE party nominee"
                    : c.list === "certified_primary"
                      ? "Certified primary"
                      : "FEC filing"}
                </span>
              </div>
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
        </section>
      ))}
    </div>
  );
}
