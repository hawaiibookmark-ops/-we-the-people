import { LookupForm } from "@/components/LookupForm";

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <p className="kicker">General election · Tuesday, November 3, 2026</p>
        <h1>Who is on your ballot, from the filings themselves.</h1>
        <p className="lede">
          A nonpartisan voter hub. Candidates, incumbent vote links, and donors from official
          sources only. Every fact carries a source URL and a retrieval time. If two official
          sources disagree, both are shown and flagged. Votes and donor names are never invented.
        </p>
        <LookupForm />
      </section>
      <section className="grid">
        <article className="note">
          <h2>Hawaiʻi gold template</h2>
          <p className="muted">
            ZIP, address, or island lookup. Federal races from the Office of Elections certified
            2026 primary plus FEC filings. State nominees from that same certified summary. Donor
            names from official FEC bulk Schedule A ($200+) and the Hawaii Campaign Spending
            Commission SODA extract. Names are never invented. Donor lists are not sold.
          </p>
        </article>
        <article className="note">
          <h2>Other 49 states</h2>
          <p className="muted">
            FEC 2026 House and Senate filings for the Census-mapped district. State filings are
            not wired yet — that gap is labeled instead of filled with a third-party scorecard.
          </p>
        </article>
        <article className="note">
          <h2>Always free to look up</h2>
          <p className="muted">
            Founding Pro is $5/month for alerts, a saved district, CSV export, and monitored-race
            chat. Those extras are on a founding waitlist until they ship. No candidate ads.
          </p>
        </article>
      </section>
    </>
  );
}
