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
python3 scripts/build_data.py   # refresh Census / OE / FEC extracts (needs network)
npm install
npm run dev
```

Open http://localhost:3000/-we-the-people/ (the app is mounted at the GitHub Pages repo path).

Test lookups: `96813`, `90210`, `82001`.

`FEC_API_KEY` is optional. Without it, federal Schedule A $200+ donor names stay honest-empty and link to FEC. Hawaiʻi Campaign Spending Commission donors are linked to [CSC Public](https://csc.hawaii.gov/CFSPublic/), not copied.

## Deploy (GitHub Pages, $0)

This repo deploys a Next.js static export with GitHub Actions (no Vercel).

1. Push to `main`.
2. Settings → Pages → Source: **GitHub Actions** (if Pages is not already on).
3. Public URL: https://hawaiibookmark-ops.github.io/-we-the-people/

The workflow is `.github/workflows/pages.yml`. User-Agent for extracts: `WeThePeople-CivicBot/1.0`.
