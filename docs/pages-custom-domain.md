# getwethepeople.com — re-enable after DNS

Do **not** publish `public/CNAME` or set Pages `cname` while Porkbun still parks `getwethepeople.com` / `www` (`207.207.210.x`, `uixie.porkbun.com`, `getwethepeople-com.l.ink`). GitHub will 301 `https://hawaiibookmark-ops.github.io/-we-the-people/` to the custom domain and the public hub goes offline.

Live service stays on github.io until Network ops (Everything Claude) cuts DNS over.

## Confirm DNS first

Apex `A`/`AAAA` must be GitHub Pages (not Porkbun parking). `www` must CNAME to `hawaiibookmark-ops.github.io` (org host only, no repo path).

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

```bash
dig getwethepeople.com +noall +answer -t A
dig getwethepeople.com +noall +answer -t AAAA
dig www.getwethepeople.com +noall +answer -t CNAME
```

Source: [Managing a custom domain for GitHub Pages](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site). This repo does not control Porkbun.

## Then re-enable (only after the digs match)

1. Add `public/CNAME` containing exactly `getwethepeople.com`.
2. Settings → Pages → Custom domain: `getwethepeople.com` → Save (or `PUT /repos/hawaiibookmark-ops/-we-the-people/pages` with `cname=getwethepeople.com` and `build_type=workflow`).
3. After GitHub verifies DNS, enable **Enforce HTTPS**.
4. The Next app is already built for apex `/` on the custom domain (`siteBase()` is empty on `getwethepeople.com` / `www`). github.io keeps `/-we-the-people` prefixes at runtime.
