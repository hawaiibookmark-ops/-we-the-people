#!/usr/bin/env python3
"""Official NYSBOE Who Filed 2026 primary + general (complete=false)."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T17:06:00Z"
LANDING = "https://publicreporting.elections.ny.gov/WhoFiled/WhoFiled"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "ny"
STUB = ROOT / "public" / "data" / "ny.json"
CACHE = Path("/tmp/ny-whofiled")
EXPECT = 1685
EXPECT_PRI = 1338
EXPECT_GEN = 347
EXPECT_KEYS = 175
STREET_KEYS = {"street", "address", "addr", "mailing_address", "email", "phone", "zip", "zipcode"}

FILES = (
    {
        "file": "who-filed-2026-primary.csv",
        "list_kind": "who_filed_primary",
        "election": "2026 Primary Election",
        "election_date": "2026-06-23",
        "expect": EXPECT_PRI,
    },
    {
        "file": "who-filed-2026-general.csv",
        "list_kind": "who_filed_general",
        "election": "2026 General Election",
        "election_date": "2026-11-03",
        "expect": EXPECT_GEN,
    },
)


def full_name(row: dict) -> str:
    parts = [
        (row.get("Candidate First Name") or "").strip(),
        (row.get("Candidate Middle Name") or "").strip(),
        (row.get("Candidate Last Name") or "").strip(),
        (row.get("Candidate Suffix") or "").strip(),
    ]
    name = " ".join(p for p in parts if p)
    if not name:
        raise SystemExit("Who Filed row missing official candidate name")
    return name


def iso_date(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if len(raw) == 10 and raw[2] == "/" and raw[5] == "/":
        mm, dd, yyyy = raw.split("/")
        return f"{yyyy}-{mm}-{dd}"
    return raw


def parse_csv(spec: dict) -> list[dict]:
    path = CACHE / spec["file"]
    if not path.exists():
        raise SystemExit(f"missing official Who Filed CSV {path} (do not invent names)")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows_in = list(csv.DictReader(fh))
    if len(rows_in) != spec["expect"]:
        raise SystemExit(f"{spec['file']} rows {len(rows_in)} != {spec['expect']}")
    out = []
    for row in rows_in:
        office = (row.get("Office") or "").strip()
        dist = (row.get("District") or "").strip() or None
        dist2 = (row.get("District 2") or "").strip() or None
        rec = {
            "state": "NY",
            "contest_key": f"NY|{office}|{dist or ''}|{dist2 or ''}",
            "office": office,
            "district": dist,
            "candidate_office": office,
            "party": (row.get("Party") or "").strip() or None,
            "candidate_name": full_name(row),
            "list_kind": spec["list_kind"],
            "election": spec["election"],
            "election_year": "2026",
            "election_date": spec["election_date"],
            "candidate_status": (row.get("CandidateStatus") or "").strip() or None,
            "date_filed": iso_date(row.get("Date Filed") or ""),
            "office_type": (row.get("Office Type") or "").strip() or None,
            "complete": False,
            "source_url": LANDING,
            "retrieved_at": RETRIEVED,
        }
        if STREET_KEYS & {k.lower() for k in rec}:
            raise SystemExit("street field leaked into NY Who Filed row")
        out.append(rec)
    return out


def write_stub(rows: list[dict]) -> None:
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    fec = ((stub.get("state_filings") or {}).get("federal_fec") or {}).copy()
    if donors.get("path") != "/data/ny/nysboe-donors.json":
        raise SystemExit("refusing to wipe NY NYSBOE donors")
    if fec.get("path") != "/data/ny/fec-donors.json":
        raise SystemExit("refusing to wipe NY FEC donors")
    if stub.get("votes_path") != "/data/ny/votes.json":
        raise SystemExit("refusing to wipe NY votes_path")
    kinds = Counter(r["list_kind"] for r in rows)
    stub["election"] = {
        "jurisdiction": "New York",
        "state_code": "NY",
        "general_date": "2026-11-03",
        "note": (
            "Official NYSBOE Who Filed 2026 primary + general (complete=false), "
            "NYSBOE Schedule A–D donors (Open NY e9ss-239a), Clerk/LIS federal votes, "
            "and federal FEC Schedule A $200+. Donor lists are not sold."
        ),
    }
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["donors"] = donors
    filings["federal_fec"] = fec
    filings["who_filed"] = LANDING
    filings["candidates"] = {
        "status": "partial",
        "path": "/data/ny/candidates.json",
        "source_url": LANDING,
        "retrieved_at": RETRIEVED,
        "complete": False,
        "counts": {
            "rows": len(rows),
            "primary": kinds.get("who_filed_primary", 0),
            "general": kinds.get("who_filed_general", 0),
            "contest_keys": len({r["contest_key"] for r in rows}),
        },
        "do_not_sell_donor_lists": True,
    }
    stub["candidates_path"] = "/data/ny/candidates.json"
    stub["candidate_summary_path"] = "/data/ny/candidate-summary.json"
    stub["votes_path"] = "/data/ny/votes.json"
    stub["congress_delegation_path"] = "/data/ny/congress-delegation.json"
    stub["legislature_vote_index_path"] = "/data/ny/legislature-vote-index.json"
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {
            "url": LANDING,
            "retrieved_at": RETRIEVED,
            "note": "Official NYSBOE Who Filed 2026 primary + general (complete=false)",
        }
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    rows: list[dict] = []
    for spec in FILES:
        rows.extend(parse_csv(spec))
    if len(rows) != EXPECT:
        raise SystemExit(f"NY Who Filed {len(rows)} != {EXPECT}")
    kinds = Counter(r["list_kind"] for r in rows)
    if kinds.get("who_filed_primary") != EXPECT_PRI or kinds.get("who_filed_general") != EXPECT_GEN:
        raise SystemExit(f"NY list_kind split {dict(kinds)} != {EXPECT_PRI}/{EXPECT_GEN}")
    keys = {r["contest_key"] for r in rows}
    if len(keys) != EXPECT_KEYS:
        raise SystemExit(f"NY contest_keys {len(keys)} != {EXPECT_KEYS}")
    if any(str(k).count("|") != 3 for k in keys):
        raise SystemExit("NY contest_key must be NY|OFFICE|DIST|DIST2")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not (OUT_DIR / "nysboe-donors.json").exists() or not (OUT_DIR / "fec-donors.json").exists():
        raise SystemExit("refusing to write NY candidates without existing donor extracts")
    if not (OUT_DIR / "votes.json").exists():
        raise SystemExit("refusing to write NY candidates without existing votes")
    (OUT_DIR / "candidates.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "row_count": len(rows),
        "contest_key_count": len(keys),
        "list_kind": sorted(kinds),
        "by_list_kind": dict(kinds),
        "complete": False,
        "certified": False,
        "source_url": LANDING,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official NYSBOE Who Filed CSV export for 2026 Primary (06/23/2026) and "
            "General (11/03/2026). Only candidates who file with NYSBOE. "
            "complete=false. Streets omitted. No Ballotpedia."
        ),
        "user_agent": UA,
    }
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub(rows)
    print(
        f"wrote NY Who Filed {len(rows)} pri={kinds['who_filed_primary']} "
        f"gen={kinds['who_filed_general']} keys={len(keys)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
