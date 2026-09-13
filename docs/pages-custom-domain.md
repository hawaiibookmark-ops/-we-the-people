# getwethepeople.com — attach apex (admin Save)

DNS A records already point at GitHub Pages. This repo does not control Porkbun and does not change DNS.

`GET /repos/hawaiibookmark-ops/-we-the-people/pages` (2026-09-13): `cname: null`, `build_type: workflow`, `https_enforced: true`, `html_url` still github.io. Apex and www HTTPS return GitHub Pages **404 "Site not found"** (domain not attached). github.io hub is **200**.

Cursor agent and `GITHUB_TOKEN` **403** on `PUT /repos/.../pages` (`admin: false`). Actions-published sites **ignore** artifact `CNAME`. A repo admin must Save the apex in Settings.

## Do not

- Do **not** type `www.getwethepeople.com` in Custom domain (past failure: github.io 301 → parked www; later apex↔www 301 loop).
- Do **not** set www as a second primary.
- Do **not** leave github.io 301ing to apex while apex is still 404. Click **Remove** immediately.
- Do **not** change Porkbun. A records are already `185.199.108/109/110/111.153`. `www` CNAME is already `hawaiibookmark-ops.github.io`.

## Jeff: Save apex only

1. Open [Settings → Pages](https://github.com/hawaiibookmark-ops/-we-the-people/settings/pages) while logged in as a repo admin (Jeff Gomes / `hawaiibookmark-ops`).
2. Under **Custom domain**, type exactly `getwethepeople.com` (apex only).
3. Click **Save**.
4. Wait for the DNS check checkmark. Do **not** treat www as a second custom domain.
5. In another tab, immediately:

```bash
curl -sI https://getwethepeople.com/
curl -sI https://hawaiibookmark-ops.github.io/-we-the-people/
```

6. **Rollback if needed:** if github.io is `301`/`302` to `getwethepeople.com` and apex is still `404` "Site not found", click **Custom domain → Remove**. That restores github.io. Do not leave the public hub on a 301-to-404.
7. **After** `curl -sI https://getwethepeople.com/` is `200` and the body is the We The People hub, check **Enforce HTTPS** if the checkbox is available and not already green. Then www may one-way 301 → apex (GitHub does this when the configured domain is the apex and `www` DNS exists). Never apex → www.

Equivalent API (admin token only; this agent 403s):

```bash
gh api -X PUT repos/hawaiibookmark-ops/-we-the-people/pages \
  -f cname=getwethepeople.com \
  -f build_type=workflow
# after apex HTTPS 200 hub only:
# gh api -X PUT repos/hawaiibookmark-ops/-we-the-people/pages \
#   -f cname=getwethepeople.com -f build_type=workflow -F https_enforced=true
```

## App already built for both hosts

- Next export has **no `basePath`**. Apex `/` is `/lookup/`, `/data/…`.
- On `*.github.io`, `siteBase()` prefixes links and JSON with `/-we-the-people`.
- CI `assetPrefix` is `https://hawaiibookmark-ops.github.io/-we-the-people` so one export’s JS/CSS load on both hosts if github.io stays 200, or follow a 301 to a working apex.

## Observed DNS (2026-09-13, this network)

| Type | Host | Value |
| --- | --- | --- |
| A | `@` | `185.199.108.153` `109.153` `110.153` `111.153` |
| AAAA | `@` | *(none observed)* |
| CNAME | `www` | `hawaiibookmark-ops.github.io` |

AAAA is optional. This repo does not change DNS.
