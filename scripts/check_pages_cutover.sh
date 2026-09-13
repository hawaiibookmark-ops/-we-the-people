#!/usr/bin/env bash
# Report Pages custom-domain state. Never set www. Never leave github.io 301 → 404.
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-hawaiibookmark-ops/-we-the-people}"
APEX="https://getwethepeople.com/"
GITHUB_IO="https://hawaiibookmark-ops.github.io/-we-the-people/"
WWW="https://www.getwethepeople.com/"

hub_ok() {
  local url="$1"
  local body
  body="$(curl -fsS "$url" || true)"
  printf '%s' "$body" | grep -q "We The People"
}

echo "=== GET /repos/${REPO}/pages ==="
gh api "repos/${REPO}/pages" || true
cname="$(gh api "repos/${REPO}/pages" --jq '.cname // empty' 2>/dev/null || true)"
https_enforced="$(gh api "repos/${REPO}/pages" --jq '.https_enforced' 2>/dev/null || true)"
echo "pages.cname=${cname:-<empty>}"
echo "pages.https_enforced=${https_enforced:-<unknown>}"

echo
echo "=== curl -sI ${GITHUB_IO} ==="
curl -sI "$GITHUB_IO" | tr -d '\r'
io_code="$(curl -sI -o /dev/null -w '%{http_code}' "$GITHUB_IO")"
io_loc="$(curl -sI "$GITHUB_IO" | tr -d '\r' | awk 'tolower($1)=="location:"{print $2; exit}')"

echo
echo "=== curl -sI ${APEX} ==="
curl -sI "$APEX" | tr -d '\r'
apex_code="$(curl -sI -o /dev/null -w '%{http_code}' "$APEX")"
apex_loc="$(curl -sI "$APEX" | tr -d '\r' | awk 'tolower($1)=="location:"{print $2; exit}')"

echo
echo "=== curl -sI ${WWW} ==="
curl -sI "$WWW" | tr -d '\r' || true
www_code="$(curl -sI -o /dev/null -w '%{http_code}' "$WWW" || true)"

echo
echo "summary: github.io=${io_code} location=${io_loc:-none} apex=${apex_code} location=${apex_loc:-none} www=${www_code:-err}"

# Safety: github.io must stay 200 with hub, or 301/302 only to a working apex HTTPS 200.
if [[ "$io_code" == "200" ]]; then
  if hub_ok "$GITHUB_IO"; then
    echo "OK github.io 200 hub"
  else
    echo "::error::github.io 200 but body is not the We The People hub"
    exit 1
  fi
elif [[ "$io_code" == "301" || "$io_code" == "302" || "$io_code" == "307" || "$io_code" == "308" ]]; then
  case "${io_loc}" in
    https://getwethepeople.com|https://getwethepeople.com/|https://getwethepeople.com/-we-the-people|https://getwethepeople.com/-we-the-people/)
      if [[ "$apex_code" == "200" ]] && hub_ok "$APEX"; then
        echo "OK github.io ${io_code} → working apex HTTPS 200 hub"
      else
        echo "::error::CRITICAL: github.io ${io_code} → ${io_loc} but apex is ${apex_code} (not hub 200). Remove Custom domain now: Settings → Pages → Custom domain → Remove."
        exit 1
      fi
      ;;
    *)
      echo "::error::CRITICAL: github.io ${io_code} → ${io_loc:-none} is not the apex hub. Remove Custom domain if it is set."
      exit 1
      ;;
  esac
else
  echo "::error::github.io returned ${io_code}; expected 200 or redirect to working apex"
  exit 1
fi

if [[ -n "${cname}" && "${cname}" == "www.getwethepeople.com" ]]; then
  echo "::error::Pages cname is www (second primary). Set apex only: getwethepeople.com. Past failure was apex↔www 301 loop."
  exit 1
fi

if [[ "$apex_code" == "200" ]] && hub_ok "$APEX"; then
  echo "OK apex HTTPS 200 hub"
elif [[ -z "${cname}" ]]; then
  echo "::notice::apex is ${apex_code} and pages.cname is empty. Repo admin must Save getwethepeople.com in Settings → Pages (API PUT is 403 for GITHUB_TOKEN / this agent)."
else
  echo "::warning::pages.cname=${cname} but apex HTTPS is ${apex_code}. Wait for DNS check / cert, or Remove if github.io would 301 to 404."
fi
