#!/usr/bin/env python3
"""Official Illinois SBE Latest Candidates Filed RSS (not a certified roster)."""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T12:56:30Z"
ELECTION_ID = "sejIrI+Qmww="
LANDING = "https://elections.il.gov/ElectionOperations/CandidatesFiled.aspx"
RSS_URL = f"https://elections.il.gov/RSS/LatestCandidatesFiled.aspx?ID={urllib.parse.quote(ELECTION_ID)}"
LIST_KIND = "latest_filed_rss"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "il"
STUB = ROOT / "public" / "data" / "il.json"
CACHE = Path("/tmp/il-sbe/candidates.rss")
EXPECT = 528
DESC_RE = re.compile(
    r"(?:Address:\s*(?P<address>.*?)<br\s*/?>)?\s*Office:\s*(?P<office>.*?)<br\s*/?>\s*Party:\s*(?P<party>.*)",
    re.I | re.S,
)
DIST_RE = re.compile(r"(\d+)(?:ST|ND|RD|TH)\s+(SENATE|REPRESENTATIVE|CONGRESS)\b", re.I)
CIRCUIT_RE = re.compile(r"^(.+?(?:CIRCUIT|SUBCIRCUIT).*)$", re.I)


def contest_key(office: str, district: str | None) -> str:
    return f"IL|{office}|{district or ''}|"


def split_office(office: str) -> tuple[str, str | None]:
    m = DIST_RE.search(office)
    if m:
        kind = m.group(2).title()
        if kind == "Congress":
            office_name = "United States Representative"
        elif kind == "Senate":
            office_name = "State Senator"
        else:
            office_name = "State Representative"
        return office_name, m.group(1)
    return office, None


def fetch_rss() -> bytes:
    if CACHE.exists() and CACHE.stat().st_size > 10_000:
        raw = CACHE.read_bytes()
        if raw.startswith(b"<?xml"):
            return raw
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": UA, "Accept": "application/rss+xml,text/xml,*/*"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
    CACHE.write_bytes(raw)
    if not raw.startswith(b"<?xml"):
        raise SystemExit("IL SBE RSS did not return XML")
    return raw


def parse_rows(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    rows: list[dict] = []
    for item in root.findall(".//item"):
        name = html.unescape((item.findtext("title") or "").strip())
        desc = html.unescape((item.findtext("description") or "").strip())
        link = (item.findtext("link") or "").strip()
        if not name:
            raise SystemExit("RSS item missing official candidate name")
        m = DESC_RE.search(desc.replace("\n", " "))
        office_raw = (m.group("office") if m else "").strip()
        party = (m.group("party") if m else "").strip() or None
        if not office_raw:
            raise SystemExit(f"RSS item missing office for {name!r}: {desc!r}")
        office, district = split_office(office_raw)
        if link.startswith("/"):
            source_detail = urllib.parse.urljoin("https://elections.il.gov", link)
        else:
            source_detail = link or RSS_URL
        rows.append(
            {
                "state": "IL",
                "contest_key": contest_key(office, district),
                "office": office,
                "office_raw": office_raw,
                "district": district,
                "candidate_office": office_raw,
                "party": party,
                "candidate_name": name,
                "list_kind": LIST_KIND,
                "election": "2026 General Election",
                "election_year": "2026",
                "certified": False,
                "source_url": RSS_URL,
                "detail_url": source_detail,
                "retrieved_at": RETRIEVED,
            }
        )
    if len(rows) != EXPECT:
        raise SystemExit(f"expected {EXPECT} IL RSS items, got {len(rows)}")
    return rows


def summarize(rows: list[dict]) -> dict:
    keys = {r["contest_key"] for r in rows}
    return {
        "row_count": len(rows),
        "contest_key_count": len(keys),
        "list_kind": LIST_KIND,
        "certified": False,
        "complete": False,
        "by_office": dict(Counter(r["office"] for r in rows)),
        "by_party": dict(Counter((r.get("party") or "") for r in rows)),
        "source_url": RSS_URL,
        "landing_url": LANDING,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official Illinois SBE Latest Candidates Filed RSS for the 2026 general "
            f"(ElectionID={ELECTION_ID}). RSS-partial rolling latest-filed feed only — "
            "NOT a certified full ballot. Full CandidatesFiled grid / Candidates.txt TBD. "
            "Streets from the RSS Address field are omitted. Names as filed only. No Ballotpedia."
        ),
    }


def write_stub() -> None:
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    fec = ((stub.get("state_filings") or {}).get("federal_fec") or {}).copy()
    stub["election"] = {
        "jurisdiction": "Illinois",
        "state_code": "IL",
        "general_date": "2026-11-03",
        "note": (
            "Official Illinois SBE Schedule A receipts, SBE Latest Candidates Filed RSS-partial "
            "(rolling latest-filed feed, not a certified full ballot; full CandidatesFiled grid / "
            "Candidates.txt TBD), Clerk/LIS federal votes, and federal FEC Schedule A $200+ when "
            "present. Donor lists are not sold."
        ),
    }
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["sbe_candidates_filed"] = LANDING
    filings["sbe_candidates_rss"] = RSS_URL
    if donors:
        filings["donors"] = donors
    if fec:
        filings["federal_fec"] = fec
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    stub["candidates_path"] = "/data/il/candidates.json"
    stub["candidate_summary_path"] = "/data/il/candidate-summary.json"
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": LANDING, "retrieved_at": RETRIEVED, "note": "Illinois SBE Candidates Filed (2026 general)"},
        {
            "url": RSS_URL,
            "retrieved_at": RETRIEVED,
            "note": "Official Latest Candidates Filed RSS-partial (not a certified full ballot; CandidatesFiled grid / Candidates.txt TBD)",
        },
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
        else:
            for existing in sources:
                if existing.get("url") == src["url"]:
                    existing["retrieved_at"] = RETRIEVED
                    if src.get("note"):
                        existing["note"] = src["note"]
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote stub", STUB, flush=True)


def main() -> int:
    rows = parse_rows(fetch_rss())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summarize(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub()
    print(f"wrote {len(rows)} IL RSS-partial candidates contest_keys={len({r['contest_key'] for r in rows})}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
