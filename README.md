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

Open http://localhost:3000/ (custom-domain apex; no repo path prefix).

Test lookups: `96813`, `90210`, `82001`.

Federal Schedule A $200+ names are committed in `public/data/donors.json` from official FEC bulk (`indiv26.zip` + `cn26`/`ccl26`). OpenFEC and `DEMO_KEY` are not used. Hawaiʻi CSC names are committed in `public/data/csc-donors.json` from the official SODA resource. Street addresses are omitted. Names are never invented. Donor lists are not sold.

Incumbent votes are committed in `public/data/congress-votes.json` (House Clerk EVS + Senate LIS) and `public/data/hawaii-votes.json` (named votes on official measure status pages). Votes are never invented. Unnamed unanimous floor tallies are not expanded into per-member Ayes. No Ballotpedia. No scores. Rebuild with `python3 scripts/build_votes.py`.

`python3 scripts/build_data.py` refreshes Census / OE / FEC *candidate* extracts and **preserves** the committed donor files. Do not re-download the 2GB FEC individual file on GitHub Pages.

## Deploy (GitHub Pages, $0)

This repo deploys a Next.js static export with GitHub Actions (no Vercel).

1. Push to `main`.
2. Settings → Pages → Source: **GitHub Actions** (if Pages is not already on).
3. Settings → Pages → Custom domain: **`getwethepeople.com`** then Save. This repo publishes via Actions, so a `CNAME` file in the artifact does **not** set the domain by itself (GitHub ignores it for workflow publishes). A repo admin must Save the domain in settings (or a token with “manage GitHub Pages settings” must PUT `/repos/.../pages` with `cname=getwethepeople.com`). After DNS verifies, check **Enforce HTTPS**.
4. Primary URL (after DNS cutover): https://getwethepeople.com/
5. github.io project URL still served: https://hawaiibookmark-ops.github.io/-we-the-people/

The Next export has **no `basePath`**. On `getwethepeople.com` / `www` the app is at `/`. On `*.github.io` links and `/data/*.json` are prefixed with `/-we-the-people` at runtime. CI sets `assetPrefix` to the github.io origin so one artifact’s JS/CSS load on both hosts.

### Porkbun DNS (Network ops — not this repo)

Do **not** leave Porkbun parking (`207.207.210.x` / `uixie.porkbun.com`). GitHub’s current Pages addresses (from [Managing a custom domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)):

| Type | Host | Value |
| --- | --- | --- |
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| AAAA | `@` | `2606:50c0:8000::153` |
| AAAA | `@` | `2606:50c0:8001::153` |
| AAAA | `@` | `2606:50c0:8002::153` |
| AAAA | `@` | `2606:50c0:8003::153` |
| CNAME | `www` | `hawaiibookmark-ops.github.io` |

`www` must CNAME to **`hawaiibookmark-ops.github.io`** (org Pages host — no repo path). Apex is `A`/`AAAA` (or ALIAS/ANAME to `hawaiibookmark-ops.github.io`), not a CNAME. No wildcard `*.getwethepeople.com`. Remove Porkbun link/parking records on `@` and `www` first. This agent does not control Porkbun and does not invent DNS ownership.

The workflow is `.github/workflows/pages.yml`. User-Agent for extracts: `WeThePeople-CivicBot/1.0`.
