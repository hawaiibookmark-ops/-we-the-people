# getwethepeople.com — attach only after the export serves `/`

This is a GitHub **project** Pages site. Until a custom domain is attached it is
`https://hawaiibookmark-ops.github.io/-we-the-people/`. After Settings → Pages
saves apex `getwethepeople.com`, GitHub **301s github.io to the custom domain**
and serves the **same artifact at `/`**.

If that artifact has no hub `index.html` at the publish root, apex `/` is the
GitHub Pages 404 and the 301 takes the live hub offline. **Do not Save the
domain until the VERIFY checklist below is green on the already-deployed
artifact.**

This repo must **not** publish `public/CNAME`. Actions-published sites ignore
artifact `CNAME` for the attach itself; Settings (or an admin `PUT /pages`) is
what binds the domain. `GITHUB_TOKEN` is **403** on that API (`admin: false`).
Do not treat a 403 as “try a CNAME file instead.”

## Dual-host export (what must ship)

One Next export, no `basePath`:

| Published path | Host after attach | Host before attach |
| --- | --- | --- |
| `out/index.html` | `https://getwethepeople.com/` | `https://hawaiibookmark-ops.github.io/-we-the-people/` |
| `out/lookup/`, `out/data/` | `/lookup/`, `/data/…` | `/-we-the-people/lookup/`, `/-we-the-people/data/…` |
| `out/_next/` | unused for `<script src="/-we-the-people/_next/…">` on apex | `/-we-the-people/_next/…` on github.io |
| `out/-we-the-people/index.html` | `https://getwethepeople.com/-we-the-people/` if a 301 keeps the repo path | `https://hawaiibookmark-ops.github.io/-we-the-people/-we-the-people/` |
| `out/-we-the-people/_next/` | same-origin assets for `assetPrefix: '/-we-the-people'` on apex | safety copy |

`assetPrefix` is the **path** `/-we-the-people`, never
`https://hawaiibookmark-ops.github.io/-we-the-people`. The github.io origin 301s
to apex once the domain is attached; JS/CSS must not depend on it.

`siteBase()` prefixes links and `/data/*.json` when the path already starts with
`/-we-the-people` or the host is `*.github.io`. On `getwethepeople.com` at `/`
it is empty.

## VERIFY checklist (do this before Save)

### 1. Local preview of the export root (no domain attach)

```bash
python3 scripts/test_prepare_pages_export.py
npm ci
npm run build:pages
python3 -m http.server 4173 --directory out
```

| Request | Must be |
| --- | --- |
| `http://127.0.0.1:4173/` | **200**, HTML contains `We The People` (this is apex `/`) |
| `http://127.0.0.1:4173/lookup/?q=96813` | **200**, lookup page |
| `http://127.0.0.1:4173/data/hawaii.json` | **200**, JSON |
| `http://127.0.0.1:4173/-we-the-people/` | **200**, same hub (dual copy) |
| `http://127.0.0.1:4173/-we-the-people/lookup/` | **200** |
| `http://127.0.0.1:4173/-we-the-people/_next/static/` | CSS/JS files exist |
| `http://127.0.0.1:4173/CNAME` | **404** (file must not exist) |

Artifact layout proof (same checks CI writes to the job summary):

```bash
test -f out/index.html && grep -q "We The People" out/index.html
test -f out/lookup/index.html
test -d out/_next
test -f out/-we-the-people/index.html
test -d out/-we-the-people/_next
test ! -f out/CNAME
grep -q '/-we-the-people/_next' out/index.html
! grep -q 'https://hawaiibookmark-ops.github.io/-we-the-people/' out/index.html
```

### 2. After this PR is deployed to Pages (still no custom domain)

```bash
curl -sI https://hawaiibookmark-ops.github.io/-we-the-people/
curl -sI https://hawaiibookmark-ops.github.io/-we-the-people/-we-the-people/
```

Both must be **200** with no `Location` to `getwethepeople.com`. The
`/-we-the-people/-we-the-people/` URL is the dual-copy proof: that folder is
what apex will use for `assetPrefix` after Save.

### 3. Admin Save (only after 1 and 2)

DNS is already on GitHub Pages (Porkbun is not controlled here):

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

`www` CNAME is the **org host only** (no repo path).

1. Settings → Pages → Custom domain: `getwethepeople.com` (apex only) → Save.
   Do not type `www.getwethepeople.com`.
2. Immediately:

```bash
curl -sI https://getwethepeople.com/
curl -sI https://hawaiibookmark-ops.github.io/-we-the-people/
```

3. Apex `/` must be **200** with We The People HTML. github.io **may 301 to
   apex** — that is expected. Therefore apex must already serve `/` before Save.
4. If github.io is 301/302 to apex and apex is still a GitHub 404, click
   **Custom domain → Remove**. Do not leave the hub 301ing to an empty root.
5. After apex HTTPS is 200, turn on **Enforce HTTPS** if it is not already
   green. www may one-way 301 → apex. Never apex → www.

Equivalent API (admin token only; this agent 403s):

```bash
gh api -X PUT repos/hawaiibookmark-ops/-we-the-people/pages \
  -f cname=getwethepeople.com \
  -f build_type=workflow
```

Do not send `https_enforced=true` in the same request.

Source: [Managing a custom domain for GitHub Pages](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site).
