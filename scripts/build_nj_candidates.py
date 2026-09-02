#!/usr/bin/env python3
"""Official NJ Division of Elections federal candidate PDFs (primary + general)."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T16:10:00Z"
LANDING = "https://nj.gov/state/elections/election-information-2026.shtml"
BASE = "https://www.nj.gov/state/elections/assets/pdf/election-results/2026/"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "nj"
STUB = ROOT / "public" / "data" / "nj.json"
CACHE = Path("/tmp/nj-sos")
EXPECT = 97

PDFS = (
    {
        "file": "2026-official-primary-candidates-us-senate.pdf",
        "office": "U.S. Senate",
        "list_kind": "official_primary",
        "election": "2026 Primary Election",
        "election_date": "2026-06-02",
        "expect": 5,
    },
    {
        "file": "2026-official-primary-candidates-us-house.pdf",
        "office": "U.S. House",
        "list_kind": "official_primary",
        "election": "2026 Primary Election",
        "election_date": "2026-06-02",
        "expect": 52,
    },
    {
        "file": "2026-official-general-candidates-us-senate.pdf",
        "office": "U.S. Senate",
        "list_kind": "official_general",
        "election": "2026 General Election",
        "election_date": "2026-11-03",
        "expect": 4,
    },
    {
        "file": "2026-official-general-candidates-us-house.pdf",
        "office": "U.S. House",
        "list_kind": "official_general",
        "election": "2026 General Election",
        "election_date": "2026-11-03",
        "expect": 36,
    },
)

DIST = re.compile(
    r"^(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth) Congressional District",
    re.I,
)
ORD = {
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "sixth": "6",
    "seventh": "7",
    "eighth": "8",
    "ninth": "9",
    "tenth": "10",
    "eleventh": "11",
    "twelfth": "12",
}
NAME = re.compile(
    r"^((?:[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ0-9 .,'\-]+?))(?:\s+\*)?\s{2,}((?:P\.?O\.?\s*BOX|\d).+)$"
)
WRAP = re.compile(r"^([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ\-']+)$")


def fetch_pdf(name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / name
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest
    url = BASE + name
    subprocess.check_call(["curl", "-fsSL", "-A", UA, "--max-time", "90", "-o", str(dest), url])
    return dest


def pdf_text(pdf: Path) -> str:
    txt = pdf.with_suffix(".txt")
    if not txt.exists() or txt.stat().st_size < 100:
        subprocess.check_call(["pdftotext", "-layout", str(pdf), str(txt)])
    return txt.read_text(encoding="utf-8", errors="replace")


def party_of(rest: str) -> str | None:
    # Official party/slogan sits after the address on the same line.
    # Drop street-like tokens; keep the trailing party/slogan phrase.
    parts = re.split(r"\s{2,}", rest)
    if len(parts) >= 2:
        slogan = parts[-1].strip()
        if slogan and not re.match(r"^(P\.?O\.?\s*BOX|\d)", slogan, re.I):
            return slogan
    return None


def parse_pdf(spec: dict) -> list[dict]:
    text = pdf_text(fetch_pdf(spec["file"]))
    rows: list[dict] = []
    dist = None
    pending_hyphen = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if "Candidate Totals for Party" in line:
            break
        m = DIST.search(line.strip())
        if m:
            dist = ORD[m.group(1).lower()]
            pending_hyphen = None
            continue
        if pending_hyphen:
            wm = WRAP.match(line.strip())
            if wm:
                pending_hyphen["candidate_name"] = pending_hyphen["candidate_name"] + wm.group(1)
                pending_hyphen = None
                continue
            pending_hyphen = None
        m = NAME.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        rest = m.group(2)
        party = party_of(rest)
        if spec["office"] == "U.S. Senate":
            contest_office = "U.S. Senate"
            contest_dist = None
        else:
            contest_office = "U.S. House"
            contest_dist = dist
        row = {
            "state": "NJ",
            "contest_key": f"NJ|{contest_office}|{contest_dist or ''}|",
            "office": contest_office,
            "district": contest_dist,
            "candidate_office": contest_office,
            "party": party,
            "candidate_name": name.rstrip("-").strip() if not name.endswith("-") else name,
            "list_kind": spec["list_kind"],
            "election": spec["election"],
            "election_year": "2026",
            "election_date": spec["election_date"],
            "complete": False,
            "federal_only": True,
            "source_url": BASE + spec["file"],
            "retrieved_at": RETRIEVED,
        }
        rows.append(row)
        pending_hyphen = row if name.endswith("-") else None
    if pending_hyphen and pending_hyphen["candidate_name"].endswith("-"):
        pending_hyphen["candidate_name"] = pending_hyphen["candidate_name"].rstrip("-").strip()
    if len(rows) != spec["expect"]:
        raise SystemExit(f"{spec['file']} rows {len(rows)} != {spec['expect']}")
    return rows


def write_stub(rows: list[dict]) -> None:
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    if donors.get("path") and "fec-donors" not in str(donors.get("path") or "") and donors.get("status") == "sourced":
        raise SystemExit("refusing to wipe sourced NJ state donors")
    stub["election"] = {
        "jurisdiction": "New Jersey",
        "state_code": "NJ",
        "general_date": "2026-11-03",
        "note": (
            "Official NJ Division of Elections federal_only candidate PDFs (primary + general; "
            "complete=false — state offices not included), Clerk/LIS federal votes, and "
            "federal FEC Schedule A $200+. State campaign-finance bulk is pending. "
            "Donor lists are not sold."
        ),
    }
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["nj_elections_landing"] = LANDING
    if donors:
        filings["donors"] = donors
    stub["candidates_path"] = "/data/nj/candidates.json"
    stub["candidate_summary_path"] = "/data/nj/candidate-summary.json"
    stub["votes_path"] = "/data/nj/votes.json"
    stub["congress_delegation_path"] = "/data/nj/congress-delegation.json"
    stub["legislature_vote_index_path"] = "/data/nj/legislature-vote-index.json"
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [{"url": LANDING, "retrieved_at": RETRIEVED, "note": "NJ Division of Elections 2026 information"}]
    for spec in PDFS:
        extra.append(
            {
                "url": BASE + spec["file"],
                "retrieved_at": RETRIEVED,
                "note": f"Official NJ {spec['list_kind']} {spec['office']} candidate PDF",
            }
        )
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    rows: list[dict] = []
    for spec in PDFS:
        rows.extend(parse_pdf(spec))
    if len(rows) != EXPECT:
        raise SystemExit(f"NJ candidates {len(rows)} != {EXPECT}")
    # Restore hyphenated wrap names that were split across lines.
    for row in rows:
        if row["candidate_name"] == "VERLINA REYNOLDS-JACKSON" or row["candidate_name"].startswith("VERLINA REYNOLDS"):
            row["candidate_name"] = "VERLINA REYNOLDS-JACKSON"
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
        "federal_only": True,
        "source_url": LANDING,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official New Jersey Division of Elections federal_only candidate PDFs "
            "(primary US Senate/House + general US Senate/House). State offices are "
            "not on these lists (complete=false). Streets omitted. No Ballotpedia."
        ),
    }
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub(rows)
    print(f"wrote NJ candidates {len(rows)} kinds={dict(kinds)} keys={summary['contest_key_count']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
