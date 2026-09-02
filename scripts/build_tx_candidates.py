#!/usr/bin/env python3
"""Official Texas SOS 2026 general ballot certification PDF."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T12:56:00Z"
CERT_DATE = "2026-08-28"
PDF_URL = "https://www.sos.state.tx.us/elections/forms/2026-ballot-cert.pdf"
LANDING = "https://www.sos.state.tx.us/elections/laws/2026-november-general-election.shtml"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "tx"
STUB = ROOT / "public" / "data" / "tx.json"
CACHE = Path("/tmp/tx-sos")
PDF = CACHE / "2026-ballot-cert.pdf"
PARTY_RE = re.compile(r"^(?P<name>.+?)\s+(?P<party>REP|DEM|LIB|GRE|IND)\s*$")
DIST_RE = re.compile(r"DISTRICT\s+(\d+)", re.I)
COUNTY_RE = re.compile(r"^County\s+(.+?)\s*$")
SKIP_RE = re.compile(
    r"^(Page \d+ of|08/28/2026|Texas Secretary|Ballot Certification|2026 NOVEMBER|November 03)"
)
STATE_OR_DISTRICT_PREFIXES = (
    "U. S. SENATOR",
    "U. S. REPRESENTATIVE",
    "GOVERNOR",
    "LIEUTENANT GOVERNOR",
    "ATTORNEY GENERAL",
    "COMPTROLLER",
    "COMMISSIONER OF THE GENERAL LAND OFFICE",
    "COMMISSIONER OF AGRICULTURE",
    "RAILROAD COMMISSIONER",
    "CHIEF JUSTICE, SUPREME COURT",
    "JUSTICE, SUPREME COURT",
    "JUDGE, COURT OF CRIMINAL APPEALS",
    "STATE SENATOR",
    "STATE REPRESENTATIVE",
    "MEMBER, STATE BOARD OF EDUCATION",
    "DISTRICT JUDGE",
    "DISTRICT ATTORNEY",
    "CRIMINAL DISTRICT ATTORNEY",
    "CRIMINAL DISTRICT JUDGE",
)


def is_state_or_district(office: str) -> bool:
    upper = office.upper()
    if "COURT OF APPEALS" in upper:
        return True
    return any(upper.startswith(p) for p in STATE_OR_DISTRICT_PREFIXES)


def district_token(office: str, county: str, statewide: bool) -> str | None:
    m = DIST_RE.search(office)
    if m:
        return m.group(1)
    if not statewide:
        return county
    return None


def contest_key(office: str, district: str | None) -> str:
    return f"TX|{office}|{district or ''}|"


def fetch_pdf() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    if PDF.exists() and PDF.stat().st_size > 100_000:
        return PDF
    subprocess.check_call(["curl", "-fsSL", "-A", UA, "--max-time", 120, "-o", str(PDF), PDF_URL])
    return PDF


def parse_rows(text: str) -> list[dict]:
    seen: dict[tuple, dict] = {}
    county = ""
    office = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or SKIP_RE.match(stripped):
            continue
        cm = COUNTY_RE.match(stripped)
        if cm:
            county = cm.group(1).strip()
            office = ""
            continue
        if re.match(r"^ {5}[A-Z0-9]", raw) and not PARTY_RE.search(stripped):
            office = stripped
            continue
        m = PARTY_RE.search(stripped)
        if not m or not office or not county:
            continue
        name = m.group("name").strip()
        party = m.group("party")
        statewide = is_state_or_district(office)
        key = (office, name, party) if statewide else (county, office, name, party)
        if key in seen:
            continue
        dist = district_token(office, county, statewide)
        row = {
            "state": "TX",
            "contest_key": contest_key(office, dist),
            "office": office,
            "district": dist,
            "candidate_office": office,
            "party": party,
            "candidate_name": name,
            "list_kind": "general_ballot_certification",
            "election": "2026 General Election",
            "election_year": "2026",
            "certification_date": CERT_DATE,
            "source_url": PDF_URL,
            "retrieved_at": RETRIEVED,
        }
        if not statewide:
            row["county"] = county
        seen[key] = row
    rows = list(seen.values())
    if len(rows) != 3823:
        raise SystemExit(f"unexpected TX certified rows {len(rows)} != 3823")
    return rows


def main() -> int:
    pdf = fetch_pdf()
    txt = CACHE / "cert.txt"
    if not txt.exists() or txt.stat().st_size < 1000:
        subprocess.check_call(["pdftotext", "-layout", str(pdf), str(txt)])
    rows = parse_rows(txt.read_text(encoding="utf-8", errors="replace"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    keys = {r["contest_key"] for r in rows}
    summary = {
        "row_count": len(rows),
        "contest_key_count": len(keys),
        "list_kind": "general_ballot_certification",
        "certification_date": CERT_DATE,
        "by_party": dict(Counter(r["party"] for r in rows)),
        "by_office": dict(Counter(r["office"] for r in rows)),
        "source_url": PDF_URL,
        "landing_url": LANDING,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official Texas SOS 2026 Ballot Certification PDF (final certification dated "
            "August 28, 2026). State and district offices are one row per certified name + party. "
            "County offices keep the county on contest_key. Streets omitted. No Ballotpedia. "
            "Declared write-in certification is a separate SOS exhibit and is not mixed in."
        ),
    }
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    filings = stub.setdefault("state_filings", {})
    donors = (filings.get("donors") or {}).copy()
    federal = (filings.get("federal_fec") or {}).copy()
    tec_zip = filings.get("tec_zip")
    tec_landing = filings.get("tec_landing")
    stub["election"] = {
        "jurisdiction": "Texas",
        "state_code": "TX",
        "general_date": "2026-11-03",
        "note": (
            "Official Texas SOS 2026 general ballot certification PDF (certified 2026-08-28), "
            "TEC itemized 2025–2026 contributions, Clerk/LIS federal votes, and federal FEC "
            "Schedule A $200+. Donor lists are not sold."
        ),
    }
    filings["wired"] = True
    filings["tx_sos_cert_pdf"] = PDF_URL
    filings["tx_sos_landing"] = LANDING
    if donors:
        filings["donors"] = donors
    if federal:
        filings["federal_fec"] = federal
    if tec_zip:
        filings["tec_zip"] = tec_zip
    if tec_landing:
        filings["tec_landing"] = tec_landing
    stub["candidates_path"] = "/data/tx/candidates.json"
    stub["candidate_summary_path"] = "/data/tx/candidate-summary.json"
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": PDF_URL, "retrieved_at": RETRIEVED, "note": "Texas SOS 2026 Ballot Certification PDF"},
        {"url": LANDING, "retrieved_at": RETRIEVED, "note": "Texas SOS 2026 November general election information"},
    ]
    for src in extra:
        if src["url"] in have:
            for existing in sources:
                if existing.get("url") == src["url"]:
                    existing["retrieved_at"] = RETRIEVED
        else:
            sources.append(src)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote TX candidates {len(rows)} keys {len(keys)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
