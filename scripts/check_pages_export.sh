#!/usr/bin/env bash
# Local VERIFY of the dual-host Pages export. Run after `npm run build:pages`.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/out}"

fail() { echo "FAIL: $*" >&2; exit 1; }

test -f "$OUT/index.html" || fail "out/index.html missing (apex / would 404)"
grep -q "We The People" "$OUT/index.html" || fail "out/index.html is not the hub"
grep -q '/-we-the-people/_next' "$OUT/index.html" || fail "missing path assetPrefix"
if grep -q 'https://hawaiibookmark-ops.github.io/-we-the-people/' "$OUT/index.html"; then
  fail "assets still point at the github.io origin"
fi
test -f "$OUT/lookup/index.html" || fail "out/lookup/index.html missing"
test -d "$OUT/data" || fail "out/data missing"
test -d "$OUT/_next" || fail "out/_next missing"
test -f "$OUT/-we-the-people/index.html" || fail "dual copy index missing"
test -d "$OUT/-we-the-people/_next" || fail "dual copy _next missing"
test ! -f "$OUT/CNAME" || fail "out/CNAME must not exist"

echo "OK artifact layout at $OUT"
echo "  index.html at publish root (custom-domain apex /)"
echo "  index.html at /-we-the-people/ (project path + 301-preserving hosts)"
echo "  no CNAME"
