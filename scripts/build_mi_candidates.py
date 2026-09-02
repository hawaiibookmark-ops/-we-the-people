#!/usr/bin/env python3
"""Official Michigan BOE primary + general candidate listing reports."""

from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T14:40:00Z"
PRI_URL = "https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport&electionType=PRI&electionYear=2026"
GEN_URL = "https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport&electionType=GEN&electionYear=2026"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "mi"
STUB = ROOT / "public" / "data" / "mi.json"
CACHE = Path("/tmp/mi-ballots")
DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
PARTIES = {
    "Democratic Party",
    "Republican Party",
    "Libertarian Party",
    "Green Party",
    "U.S. Taxpayers Party",
    "Natural Law Party",
    "Working Class Party",
    "No Party Affiliation",
}
SKIP = {
    "Official Candidate Listing",
    "Unofficial Candidate Listing",
    "Candidate Name",
    "Filed On",
    "Filing Method",
    "Party / Incumbent",
    "Primary Election",
    "General Election",
    "All State and Judicial Offices",
}


class Spans(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.texts: list[str] = []
        self._on = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "span":
            self._on = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "span" and self._on:
            text = "".join(self._buf).replace("\xa0", " ").strip()
            if text:
                self.texts.append(text)
            self._on = False

    def handle_data(self, data):
        if self._on:
            self._buf.append(data)


def fetch(url: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest.read_text(encoding="utf-8", errors="replace")
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        dest.write_bytes(resp.read())
    return dest.read_text(encoding="utf-8", errors="replace")


def contest_key(office: str, district: str | None) -> str:
    return f"MI|{office}|{district or ''}|"


def split_office(office: str) -> tuple[str, str | None]:
    m = re.search(r"(District|Dist\.?)\s+(\d+)", office, re.I)
    if m:
        return office, m.group(2)
    return office, None


def parse_listing(html: str, list_kind: str, source_url: str) -> list[dict]:
    p = Spans()
    p.feed(html)
    rows: list[dict] = []
    office = ""
    texts = p.texts
    status_flags = {"DISQ", "WITHD", "Withdrawn", "Withdrew", "Deceased"}
    for i, t in enumerate(texts):
        if "Position" in t:
            office = t
        if not DATE_RE.match(t) or i == 0:
            continue
        name = texts[i - 1]
        if not name or name in SKIP or name in PARTIES or DATE_RE.match(name) or "Position" in name:
            continue
        party = texts[i - 2] if i >= 2 and texts[i - 2] in PARTIES else None
        method = texts[i + 1] if i + 1 < len(texts) else None
        if method in PARTIES or (method and "Position" in method) or (method and DATE_RE.match(method)):
            method = None
        status = texts[i + 2] if i + 2 < len(texts) and texts[i + 2] in status_flags else None
        off, dist = split_office(office)
        rows.append(
            {
                "state": "MI",
                "contest_key": contest_key(off, dist),
                "office": off,
                "district": dist,
                "candidate_office": office,
                "party": party,
                "candidate_name": name,
                "list_kind": list_kind,
                "election": "2026 Primary Election" if list_kind == "primary_official_listing" else "2026 General Election",
                "election_year": "2026",
                "filing_date": t,
                "filing_method": method,
                "status_flag": status,
                "source_url": source_url,
                "retrieved_at": RETRIEVED,
            }
        )
    return rows


def main() -> int:
    pri = parse_listing(fetch(PRI_URL, CACHE / "pri.html"), "primary_official_listing", PRI_URL)
    gen = parse_listing(fetch(GEN_URL, CACHE / "gen.html"), "general_unofficial_listing", GEN_URL)
    if len(pri) != 611:
        raise SystemExit(f"expected 611 MI primary listing rows, got {len(pri)}")
    if len(gen) != 715:
        raise SystemExit(f"expected 715 MI general listing rows, got {len(gen)}")
    rows = pri + gen
    if len(rows) != 1326:
        raise SystemExit(f"expected 1326 MI rows, got {len(rows)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "row_count": 1326,
        "contest_key_count": len({r["contest_key"] for r in rows}),
        "primary_official_listing_rows": 611,
        "general_unofficial_listing_rows": 715,
        "general_expected": 720,
        "complete": False,
        "by_list_kind": dict(Counter(r["list_kind"] for r in rows)),
        "by_office": dict(Counter(r["office"] for r in rows)),
        "source_urls": [PRI_URL, GEN_URL],
        "retrieved_at": RETRIEVED,
        "note": (
            "Official Michigan Bureau of Elections candidate listing reports for 2026 "
            "(primary official + general unofficial). General listing has 715 of 720 "
            "expected rows, so complete=false. Names as filed only. Streets omitted. "
            "No Ballotpedia."
        ),
    }
    (OUT_DIR / "candidate-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    stub["election"] = {
        "jurisdiction": "Michigan",
        "state_code": "MI",
        "general_date": "2026-11-03",
        "note": (
            "Official MiTN Schedule A donors, Michigan BOE 2026 primary/general candidate "
            "listings (general 715/720 so complete=false), Clerk/LIS federal votes, and "
            "federal FEC Schedule A $200+. Donor lists are not sold."
        ),
    }
    stub.setdefault("state_filings", {})["wired"] = True
    stub["candidates_path"] = "/data/mi/candidates.json"
    stub["candidate_summary_path"] = "/data/mi/candidate-summary.json"
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    for url, note in ((PRI_URL, "MI BOE 2026 primary official candidate listing"), (GEN_URL, "MI BOE 2026 general unofficial candidate listing (715/720, complete=false)")):
        if url not in have:
            sources.append({"url": url, "retrieved_at": RETRIEVED, "note": note})
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote MI candidates pri={len(pri)} gen={len(gen)} complete=false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
