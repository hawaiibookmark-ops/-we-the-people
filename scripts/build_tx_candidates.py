#!/usr/bin/env python3
"""Official Texas SOS 2026 general ballot certification PDF."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T14:42:00Z"
PDF_URL = "https://www.sos.state.tx.us/elections/forms/2026-ballot-cert.pdf"
LANDING = "https://www.sos.state.tx.us/elections/laws/2026-november-general-election.shtml"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "tx"
STUB = ROOT / "public" / "data" / "tx.json"
CACHE = Path("/tmp/tx-sos")
PDF = CACHE / "2026-ballot-cert.pdf"
PARTY_RE = re.compile(r"^(?P<name>.+?)\s+(?P<party>REP|DEM|LIB|GRE|IND)\s*$")
DIST_RE = re.compile(r"DISTRICT\s+(\d+)", re.I)


def contest_key(office: str, district: str | None) -> str:
    return f"TX|{office}|{district or ''}|"


def split_office(office: str) -> tuple[str, str | None]:
    m = DIST_RE.search(office)
    return office, (m.group(1) if m else None)


def fetch_pdf() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    if PDF.exists() and PDF.stat().st_size > 100_000:
        return PDF
    subprocess.check_call(["curl", "-fsSL", "-A", UA, "--max-time", 120, "-o", str(PDF), PDF_URL])
    return PDF


def parse_rows(text: str) -> list[dict]:
    seen: dict[tuple[str, str, str], dict] = {}
    office = ""
    for line in text.splitlines():
        if re.match(r"^County\s+", line):
            continue
        raw = line.rstrip()
        stripped = raw.strip()
        if not stripped:
            continue
        if re.match(r"^ {5}[A-Z0-9]", raw) and not PARTY_RE.search(stripped):
            office = stripped
            continue
        m = PARTY_RE.search(stripped)
        if not m or not office:
            continue
        name = m.group("name").strip()
        party = m.group("party")
        off, dist = split_office(office)
        key = (off, name, party)
        if key in seen:
            continue
        seen[key] = {
            "state": "TX",
            "contest_key": contest_key(off, dist),
            "office": off,
            "district": dist,
            "candidate_office": office,
            "party": party,
            "candidate_name": name,
            "list_kind": "general_certified_pdf",
            "election": "2026 General Election",
            "election_year": "2026",
            "source_url": PDF_URL,
            "retrieved_at": RETRIEVED,
        }
    rows = list(seen.values())
    if not (3800 <= len(rows) <= 3840):
        raise SystemExit(f"unexpected TX certified unique rows {len(rows)}")
    return rows


def main() -> int:
    pdf = fetch_pdf()
    txt = CACHE / "cert.txt"
    if not txt.exists():
        subprocess.check_call(["pdftotext", "-layout", str(pdf), str(txt)])
    rows = parse_rows(txt.read_text(encoding="utf-8", errors="replace"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "row_count": len(rows),
        "contest_key_count": len({r["contest_key"] for r in rows}),
        "list_kind": "general_certified_pdf",
        "by_party": dict(Counter(r["party"] for r in rows)),
        "by_office": dict(Counter(r["office"] for r in rows)),
        "source_url": PDF_URL,
        "landing_url": LANDING,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official Texas SOS 2026 Ballot Certification PDF (final certification dated "
            "August 28, 2026). One row per unique office + filed name + party; county-repeated "
            "statewide names are not duplicated. Streets omitted. No Ballotpedia."
        ),
    }
    (OUT_DIR / "candidate-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    fec = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    federal = ((stub.get("state_filings") or {}).get("federal_fec") or {}).copy()
    stub["election"] = {
        "jurisdiction": "Texas",
        "state_code": "TX",
        "general_date": "2026-11-03",
        "note": (
            "Official Texas SOS 2026 general ballot certification PDF, Clerk/LIS federal votes, "
            "federal FEC Schedule A $200+, and TEC state donors when present. Donor lists are not sold."
        ),
    }
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["tx_sos_cert_pdf"] = PDF_URL
    filings["tx_sos_landing"] = LANDING
    if federal:
        filings["federal_fec"] = federal
    elif fec.get("path") == "/data/tx/fec-donors.json":
        filings["federal_fec"] = fec
    stub["candidates_path"] = "/data/tx/candidates.json"
    stub["candidate_summary_path"] = "/data/tx/candidate-summary.json"
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": PDF_URL, "retrieved_at": RETRIEVED, "note": "Texas SOS 2026 Ballot Certification PDF"},
        {"url": LANDING, "retrieved_at": RETRIEVED, "note": "Texas SOS 2026 November general election information"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote TX candidates {len(rows)} unique certified", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
