# -we-the-people

Public publish copy of **We The People**, a nonpartisan voter hub for the Tuesday, November 3, 2026 general election.

Origin (`jeff-gomes/tmp-fa5d24de97533fcc`) remains source of truth. This repository is the GitHub Pages publish copy.

## Product rules

- Official / primary sources only. No Ballotpedia or BallotReady scrape. No scores.
- Every fact has a source URL and `retrieved_at`. If sources disagree, both are shown and flagged.
- Votes and donor names are never invented.
- Hawaiʻi is the gold template (ZIP / address / island). Other states: FEC 2026 House/Senate only, with “state filings not wired yet”.
- Lookup is always free. Founding Pro is $5/month via PayPal (`_xclick-subscriptions` to hawaiibookmark@gmail.com).
- No candidate ads. No selling donor lists or user data.

## Run locally

```bash
python3 scripts/verify_data.py
npm install
npm run dev
```

Open http://localhost:3000/-we-the-people/ (the app is mounted at the GitHub Pages repo path).

Test lookups: `96813`, `90210`, `82001`.

Federal Schedule A $200+ names are committed in `public/data/donors.json` from official FEC bulk (`indiv26.zip` + `cn26`/`ccl26`). OpenFEC and `DEMO_KEY` are not used. Hawaiʻi CSC names are committed in `public/data/csc-donors.json` from the official SODA resource. Street addresses are omitted. Names are never invented. Donor lists are not sold.

Incumbent votes are committed in `public/data/congress-votes.json` (House Clerk EVS + Senate LIS) and `public/data/hawaii-votes.json` (named votes on official measure status pages). Votes are never invented. Unnamed unanimous floor tallies are not expanded into per-member Ayes. No Ballotpedia. No scores. Rebuild with `python3 scripts/build_votes.py`.

`python3 scripts/build_data.py` refreshes Census / OE / FEC *candidate* extracts and **preserves** the committed donor files. Do not re-download the 2GB FEC individual file on GitHub Pages.

## Deploy (GitHub Pages, $0)

This repo deploys a Next.js static export with GitHub Actions (no Vercel).

1. Push to `main`.
2. Settings → Pages → Source: **GitHub Actions** (if Pages is not already on).
3. Public URL: https://hawaiibookmark-ops.github.io/-we-the-people/

The workflow is `.github/workflows/pages.yml`. User-Agent for extracts: `WeThePeople-CivicBot/1.0`.
