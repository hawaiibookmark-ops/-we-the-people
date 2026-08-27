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
              {c.voteLinks && c.voteLinks.length > 0 && (
                <p className="src">
                  Incumbent votes (official links, not restated):{" "}
                  {c.voteLinks.map((v, vi) => (
                    <span key={v.url}>
                      {vi > 0 ? " · " : ""}
                      <a href={v.url} rel="noreferrer">
                        {v.label}
                      </a>
                    </span>
                  ))}
                </p>
              )}
              <p className="src">
                Donors:{" "}
                {c.donors.status === "ok"
                  ? c.donors.items
                      .slice(0, 8)
                      .map((d) => `${d.name} ${money(d.amount)}`)
                      .join("; ")
                  : c.donors.reason}{" "}
                <a href={c.donors.sourceUrl} rel="noreferrer">
                  Source
                </a>
              </p>
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
