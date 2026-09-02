#!/usr/bin/env python3
"""Mirror Origin Ohio Dir 2026-45 statewide ballots (20 rows, complete=false).

Official names are the SOS statewide filing list (Feb 4, 2026) minus
Libertarian rows and Supreme Court — 20 major-party statewide executive/Senate
tickets. US House is not on this list. Do not fetch ohiosos.gov.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T16:45:00Z"
SOURCE = "https://www.ohiosos.gov/office/media-center/categories/press-releases/2026-02-04"
LIST_KIND = "dir_2026_45"
EXPECT = 20
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "oh"
STUB = ROOT / "public" / "data" / "oh.json"
PACKAGE = Path("/workspace/wtp-live-data/50state/2026-09-02-wave3/OH/package")

# Official SOS statewide filing names already extracted (no live SOS fetch).
# Dir 2026-45 / complete=false: major-party statewide executive + U.S. Senate.
# Libertarian and Ohio Supreme Court rows are not in this 20-row extract.
ROWS = (
    ("Sherrod Brown", "U.S. Senate", "Democratic"),
    ("Jon Husted", "U.S. Senate", "Republican"),
    ("Ron Kincaid", "U.S. Senate", "Democratic"),
    ("Vivek Ramaswamy, Robert A. McColley", "Governor and Lieutenant Governor", "Republican"),
    ("Amy Acton, David Pepper", "Governor and Lieutenant Governor", "Democratic"),
    ("Heather Hill, Stuart Moats", "Governor and Lieutenant Governor", "Republican"),
    ("Casey Putsch, Kimberly C. Georgeton", "Governor and Lieutenant Governor", "Republican"),
    ("Renea Turner, Jalen Turner", "Governor and Lieutenant Governor", "Republican"),
    ("Keith Faber", "Attorney General", "Republican"),
    ("John J. Kulewicz", "Attorney General", "Democratic"),
    ("Elliott Forhan", "Attorney General", "Democratic"),
    ("Bryan Hambley", "Secretary of State", "Democratic"),
    ("Marcell Strbich", "Secretary of State", "Republican"),
    ("Allison Russo", "Secretary of State", "Democratic"),
    ("Robert Sprague", "Secretary of State", "Republican"),
    ("Frank LaRose", "Auditor of State", "Republican"),
    ("Annette Blackwell", "Auditor of State", "Democratic"),
    ("Seth Walsh", "Treasurer of State", "Democratic"),
    ("Kristina D. Roegner", "Treasurer of State", "Republican"),
    ("Jay Edwards", "Treasurer of State", "Republican"),
)


def from_package() -> list[dict] | None:
    if not PACKAGE.is_dir():
        return None
    for name in ("candidates.json", "oh-candidates.json"):
        dest = PACKAGE / name
        if dest.exists():
            payload = json.loads(dest.read_text(encoding="utf-8"))
            if isinstance(payload, list) and len(payload) == EXPECT:
                return payload
    return None


def write_stub(rows: list[dict]) -> None:
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    if donors.get("path") and "fec-donors" not in str(donors.get("path") or "") and donors.get("status") == "sourced":
        raise SystemExit("refusing to wipe sourced OH state donors")
    stub["election"] = {
        "jurisdiction": "Ohio",
        "state_code": "OH",
        "general_date": "2026-11-03",
        "note": (
            "Official Ohio SOS Dir 2026-45 statewide candidate extract (20 rows, "
            "complete=false; US House and county offices are not on this list), "
            "Clerk/LIS federal votes, and federal FEC Schedule A $200+. "
            "State campaign-finance bulk is pending. Donor lists are not sold."
        ),
        "ballots_incomplete": True,
    }
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["sos_directive"] = "2026-45"
    filings.pop("ballots", None)
    if donors:
        filings["donors"] = donors
    stub["candidates_path"] = "/data/oh/candidates.json"
    stub["candidate_summary_path"] = "/data/oh/candidate-summary.json"
    stub["votes_path"] = "/data/oh/votes.json"
    stub["congress_delegation_path"] = "/data/oh/congress-delegation.json"
    stub["legislature_vote_index_path"] = "/data/oh/legislature-vote-index.json"
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {
            "url": SOURCE,
            "retrieved_at": RETRIEVED,
            "note": "Official SOS Dir 2026-45 statewide extract (20 rows, complete=false). No live SOS re-fetch.",
        }
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_package_row(row: dict) -> dict:
    name = (row.get("candidate_name") or row.get("name") or "").strip()
    office = (row.get("office") or row.get("candidate_office") or "").strip()
    if not name or not office:
        raise SystemExit("OH package row missing official candidate_name/office")
    if office.lower().startswith("u.s. house") or office.lower().startswith("us house"):
        raise SystemExit("OH package must not invent US House rows")
    dist = row.get("district")
    if isinstance(dist, str) and dist.strip().lower() in {"statewide", "state", ""}:
        dist = None
    return {
        "state": "OH",
        "contest_key": row.get("contest_key") or f"OH|{office}|{dist or ''}|",
        "office": office,
        "district": dist,
        "candidate_office": row.get("candidate_office") or office,
        "party": (row.get("party") or "").strip() or None,
        "candidate_name": name,
        "list_kind": row.get("list_kind") or LIST_KIND,
        "election": row.get("election") or "2026 Primary Election",
        "election_year": str(row.get("election_year") or "2026"),
        "election_date": row.get("election_date") or "2026-05-05",
        "complete": False,
        "directive": row.get("directive") or "2026-45",
        "source_url": row.get("source_url") or SOURCE,
        "retrieved_at": row.get("retrieved_at") or RETRIEVED,
    }


def main() -> int:
    packaged = from_package()
    if packaged:
        rows = [normalize_package_row(r) for r in packaged]
    else:
        if len(ROWS) != EXPECT:
            raise SystemExit(f"OH hardcoded official rows {len(ROWS)} != {EXPECT}")
        rows = []
        for name, office, party in ROWS:
            rows.append(
                {
                    "state": "OH",
                    "contest_key": f"OH|{office}||",
                    "office": office,
                    "district": None,
                    "candidate_office": office,
                    "party": party,
                    "candidate_name": name,
                    "list_kind": LIST_KIND,
                    "election": "2026 Primary Election",
                    "election_year": "2026",
                    "election_date": "2026-05-05",
                    "complete": False,
                    "directive": "2026-45",
                    "source_url": SOURCE,
                    "retrieved_at": RETRIEVED,
                }
            )
    if len(rows) != EXPECT:
        raise SystemExit(f"OH candidates {len(rows)} != {EXPECT}")
    if any(r.get("complete") is not False for r in rows):
        raise SystemExit("OH candidates must stay complete=false")
    if any((r.get("office") or "").lower().startswith("u.s. house") for r in rows):
        raise SystemExit("OH must not invent US House rows")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    kinds = Counter(r["list_kind"] for r in rows)
    summary = {
        "row_count": len(rows),
        "contest_key_count": len({r["contest_key"] for r in rows}),
        "list_kind": sorted(kinds),
        "by_list_kind": dict(kinds),
        "complete": False,
        "certified": False,
        "incomplete": True,
        "directive": "2026-45",
        "source_url": SOURCE,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official Ohio SOS Dir 2026-45 statewide extract (20 rows, complete=false). "
            "US House is not on this list. Streets omitted. No live SOS re-fetch. "
            "No Ballotpedia."
        ),
        "user_agent": UA,
    }
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub(rows)
    print(f"wrote OH candidates {len(rows)} Dir 2026-45 complete=false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
