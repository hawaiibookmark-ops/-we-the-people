#!/usr/bin/env python3
"""Official NCSBE 2026 Candidate_Listing_2026.csv (primary + general, pre-cert)."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T16:05:00Z"
CSV_URL = "https://s3.amazonaws.com/dl.ncsbe.gov/Elections/2026/Candidate%20Filing/Candidate_Listing_2026.csv"
LANDING = "https://www.ncsbe.gov/results-data/candidate-lists"
LAYOUT_URL = "https://s3.amazonaws.com/dl.ncsbe.gov/Elections/layout_candidate_listing.txt"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "nc"
STUB = ROOT / "public" / "data" / "nc.json"
CACHE = Path("/tmp/nc-ncsbe/Candidate_Listing_2026.csv")
DIST_RE = re.compile(r"DISTRICT\s+(\d+)", re.I)
SEAT_RE = re.compile(r"SEAT\s+(\d+)", re.I)
EXPECT = 4256

MULTI_COUNTY_PREFIXES = (
    "US SENATE",
    "US HOUSE",
    "US PRESIDENT",
    "NC SUPREME",
    "NC COURT OF APPEALS",
    "NC STATE SENATE",
    "NC HOUSE OF",
    "NC GOVERNOR",
    "NC LIEUTENANT",
    "NC ATTORNEY",
    "NC SECRETARY",
    "NC SUPERINTENDENT",
    "NC COMMISSIONER",
    "NC TREASURER",
    "NC AUDITOR",
    "NC LABOR",
    "NC INSURANCE",
    "NC AGRICULTURE",
)


def is_multi_county(contest: str) -> bool:
    upper = contest.upper()
    return any(upper.startswith(p) for p in MULTI_COUNTY_PREFIXES)


def district_token(contest: str, county: str) -> str | None:
    m = DIST_RE.search(contest)
    if m:
        return m.group(1)
    m = SEAT_RE.search(contest)
    if m:
        return m.group(1)
    if not is_multi_county(contest):
        return county
    return None


def fetch_csv() -> Path:
    if CACHE.exists() and CACHE.stat().st_size > 1000:
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    req = Request(CSV_URL, headers={"User-Agent": UA, "Accept": "text/csv,*/*"})
    with urlopen(req, timeout=120) as resp:
        CACHE.write_bytes(resp.read())
    return CACHE


def parse_rows(path: Path) -> list[dict]:
    raw = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    seen: set[tuple] = set()
    rows: list[dict] = []
    for rec in raw:
        contest = (rec.get("contest_name") or "").strip()
        name = (rec.get("name_on_ballot") or "").strip()
        party = (rec.get("party_candidate") or "").strip() or None
        elec = (rec.get("election_dt") or "").strip()
        county = (rec.get("county_name") or "").strip() or None
        if not name or not contest or elec not in {"11/03/2026", "03/03/2026"}:
            continue
        if is_multi_county(contest):
            key = (elec, contest, name, party)
        else:
            key = (elec, contest, name, party, county)
        if key in seen:
            continue
        seen.add(key)
        dist = district_token(contest, county or "")
        list_kind = "ncsbe_general" if elec == "11/03/2026" else "ncsbe_primary"
        row = {
            "state": "NC",
            "contest_key": f"NC|{contest}|{dist or ''}|",
            "office": contest,
            "district": dist,
            "candidate_office": contest,
            "party": party,
            "candidate_name": name,
            "list_kind": list_kind,
            "election": "2026 General Election" if list_kind == "ncsbe_general" else "2026 Primary Election",
            "election_year": "2026",
            "election_date": elec,
            "filing_date": (rec.get("candidacy_dt") or "").strip() or None,
            "complete": False,
            "source_url": CSV_URL,
            "retrieved_at": RETRIEVED,
        }
        if not is_multi_county(contest) and county:
            row["county"] = county
        rows.append(row)
    if len(rows) != EXPECT:
        raise SystemExit(f"NCSBE unique rows {len(rows)} != {EXPECT}")
    return rows


def write_stub(rows: list[dict]) -> None:
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    filings = stub.setdefault("state_filings", {})
    donors = (filings.get("donors") or {}).copy()
    if donors.get("path") and "fec-donors" not in str(donors.get("path") or "") and donors.get("status") == "sourced":
        raise SystemExit("refusing to wipe sourced NC state donors")
    stub["election"] = {
        "jurisdiction": "North Carolina",
        "state_code": "NC",
        "general_date": "2026-11-03",
        "note": (
            "Official NCSBE 2026 Candidate_Listing_2026.csv (primary + general; November list "
            "not yet final), Clerk/LIS federal votes, and federal FEC Schedule A $200+. "
            "State campaign-finance bulk is pending. Donor lists are not sold."
        ),
    }
    filings["wired"] = True
    filings["ncsbe_candidates_csv"] = CSV_URL
    filings["ncsbe_landing"] = LANDING
    if donors:
        filings["donors"] = donors
    stub["candidates_path"] = "/data/nc/candidates.json"
    stub["candidate_summary_path"] = "/data/nc/candidate-summary.json"
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": CSV_URL, "retrieved_at": RETRIEVED, "note": "Official NCSBE 2026 candidate listing CSV"},
        {"url": LANDING, "retrieved_at": RETRIEVED, "note": "NCSBE candidate lists landing"},
        {"url": LAYOUT_URL, "retrieved_at": RETRIEVED, "note": "NCSBE candidate listing layout"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    rows = parse_rows(fetch_csv())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    kinds = Counter(r["list_kind"] for r in rows)
    summary = {
        "row_count": len(rows),
        "contest_key_count": len({r["contest_key"] for r in rows}),
        "list_kind": sorted(kinds),
        "by_list_kind": dict(kinds),
        "complete": False,
        "certified": False,
        "source_url": CSV_URL,
        "landing_url": LANDING,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official NCSBE Candidate_Listing_2026.csv. Statewide/federal/legislative names are "
            "deduped across county repeats. Local contests keep county. Streets, phone, and email "
            "omitted. November general is not yet final (complete=false). No Ballotpedia."
        ),
    }
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub(rows)
    print(f"wrote NC candidates {len(rows)} kinds={dict(kinds)} keys={summary['contest_key_count']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
