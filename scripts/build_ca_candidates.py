#!/usr/bin/env python3
"""Parse official CA SOS certified candidate PDF into candidates.json."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
PDF_URL = "http://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"
RETRIEVED = "2026-09-02T11:21:25Z"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "ca"
STUB = ROOT / "public" / "data" / "ca.json"

PARTIES = (
    "Democratic",
    "Republican",
    "Libertarian",
    "Non-Partisan",
    "No Party Preference",
    "American Independent",
    "Green",
    "Peace and Freedom",
)
PARTY_RE = re.compile(
    r"^\s{2,}(.+?)\s{2,}(" + "|".join(re.escape(p) for p in PARTIES) + r")\s*$"
)
HEADER_SKIP = re.compile(
    r"^("
    r"CERTIFIED LIST OF CANDIDATES|"
    r"NOVEMBER 3, 2026, GENERAL ELECTION|"
    r"OFFICE OF THE SECRETARY OF STATE|"
    r"STATE OF CALIFORNIA|"
    r"General Election - November 3, 2026|"
    r"Official Certified List of Candidates|"
    r"Page \d+ of \d+|"
    r"8/27/2026|"
    r"I, Shirley|"
    r"That the following list|"
    r"Primary Election, and the names|"
    r"Dated at Sacramento|"
    r"\* Incumbent|"
    r"do hereby certify"
    r")",
    re.I,
)
COVER_ALLCAPS = re.compile(r"^SECRETARY OF STATE$")
CONTEST_RE = re.compile(
    r"^\s*(Governor|Lieutenant Governor|Secretary of State|Controller|Treasurer|"
    r"Attorney General|Insurance Commissioner|Superintendent of Public Instruction|"
    r"Board of Equalization Member District\s+(\d+)|"
    r"United States Representative District\s+(\d+)|"
    r"State Senate District\s+(\d+)|"
    r"State Assembly Member District\s+(\d+))\s*$"
)
SHALL_NAME = re.compile(
    r"Shall\s+(?:Associate Justice of the Supreme Court|"
    r"Administrative Presiding Justice|"
    r"Presiding Justice|"
    r"Associate Justice|"
    r"San Diego County Superior Court Judge|"
    r"Superior Court Judge|"
    r"DAVID B\. SAPP)\s+"
    r"(.+?)\s+be elected",
    re.I | re.S,
)
# DAVID B. SAPP line is "Shall DAVID B. SAPP be elected" — handled separately
SAPP_RE = re.compile(r"Shall\s+DAVID B\. SAPP\s+be elected", re.I)
JUSTICE_NAME = re.compile(
    r"Shall\s+(?:.+?)\s([A-Z][A-Z .'\-]+?)\s+be elected",
    re.S,
)

STATEWIDE = {
    "Governor": ("Governor", None),
    "Lieutenant Governor": ("Lieutenant Governor", None),
    "Secretary of State": ("Secretary of State", None),
    "Controller": ("Controller", None),
    "Treasurer": ("Treasurer", None),
    "Attorney General": ("Attorney General", None),
    "Insurance Commissioner": ("Insurance Commissioner", None),
    "Superintendent of Public Instruction": ("Superintendent of Public Instruction", None),
}


def contest_key(office: str, dist: str | None = None, vacancy: str | None = None) -> str:
    return f"CA|{office}|{dist or ''}|{vacancy or ''}"


def fetch_official_text() -> str:
    work = Path("/tmp/ca-sos")
    work.mkdir(parents=True, exist_ok=True)
    pdf = work / "cert-list-candidates.pdf"
    txt = work / "cert-list-candidates.txt"
    subprocess.check_call(
        [
            "curl",
            "-L",
            "-A",
            UA,
            "-o",
            str(pdf),
            PDF_URL,
        ]
    )
    subprocess.check_call(["pdftotext", "-layout", str(pdf), str(txt)])
    return txt.read_text(encoding="utf-8", errors="replace")


def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("*", "")).strip()


def contest_from_header(line: str) -> dict | None:
    s = line.strip()
    if s in STATEWIDE:
        office, dist = STATEWIDE[s]
        return {"contest_key": contest_key(office, dist), "office": office, "district": dist}
    m = re.match(r"Board of Equalization Member District\s+(\d+)\s*$", s)
    if m:
        d = m.group(1)
        office = "Board of Equalization Member"
        return {"contest_key": contest_key(office, d), "office": office, "district": d}
    m = re.match(r"United States Representative District\s+(\d+)\s*$", s)
    if m:
        d = m.group(1)
        office = "United States Representative"
        return {"contest_key": contest_key(office, d), "office": office, "district": d}
    m = re.match(r"State Senate District\s+(\d+)\s*$", s)
    if m:
        d = m.group(1)
        office = "State Senate"
        return {"contest_key": contest_key(office, d), "office": office, "district": d}
    m = re.match(r"State Assembly Member District\s+(\d+)\s*$", s)
    if m:
        d = m.group(1)
        office = "State Assembly Member"
        return {"contest_key": contest_key(office, d), "office": office, "district": d}
    return None


def parse_partisan(text: str) -> list[dict]:
    rows = []
    contest = None
    pending_name = None
    pending_party = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip() == "\x0c" or "\x0c" in line[:2]:
            continue
        if HEADER_SKIP.search(line.strip()) or COVER_ALLCAPS.match(line.strip()):
            continue
        if re.match(r"^Page \d+ of \d+", line.strip()):
            continue
        if re.match(r"^Shirley N\. Weber, Ph\.D\.\s*$", line.strip()):
            continue
        if "Supreme Court" in line or "Court of Appeal" in line and "Shall" not in line:
            if contest_from_header(line.strip()) is None and "District" in line or "Supreme Court -" in line:
                contest = None
                pending_name = None
                continue
        header = contest_from_header(line)
        if header:
            contest = header
            pending_name = None
            pending_party = None
            continue
        m = PARTY_RE.match(line)
        if m and contest:
            if pending_name and pending_party:
                rows.append(make_row(contest, pending_name, pending_party, None))
            pending_name = clean_name(m.group(1))
            pending_party = m.group(2)
            continue
        if pending_name and contest and line.startswith(" ") and not PARTY_RE.match(line):
            desig = clean_name(line)
            if desig and not HEADER_SKIP.search(desig) and "Shall " not in desig:
                rows.append(make_row(contest, pending_name, pending_party, desig))
                pending_name = None
                pending_party = None
                continue
        if pending_name and contest:
            rows.append(make_row(contest, pending_name, pending_party, None))
            pending_name = None
            pending_party = None
    if pending_name and contest:
        rows.append(make_row(contest, pending_name, pending_party, None))
    return rows


def make_row(contest: dict, name: str, party: str | None, designation: str | None) -> dict:
    return {
        "state": "CA",
        "contest_key": contest["contest_key"],
        "office": contest["office"],
        "district": contest["district"],
        "party": party,
        "candidate_name": name,
        "ballot_designation": designation,
        "list_kind": "general_certified_pdf",
        "source_url": PDF_URL,
        "retrieved_at": RETRIEVED,
    }


def parse_judicial(text: str) -> list[dict]:
    # Join wrapped shall-questions
    blob = re.sub(r"\n+", "\n", text)
    # Work from judicial section onward
    idx = blob.find("Supreme Court - For all 58 Counties")
    if idx < 0:
        raise RuntimeError("judicial section not found")
    section = blob[idx:]
    # Reconstruct each Shall ... law? block
    shall_bits = re.findall(
        r"Shall\s+(.+?)\s+be elected to(?:\s+the)?\s*(?:office for the term provided by law\??)?",
        section,
        flags=re.S | re.I,
    )
    # Better: grab full questions
    questions = re.findall(r"Shall\s+.+?law\?", section, flags=re.S)
    rows = []
    for q in questions:
        q1 = re.sub(r"\s+", " ", q)
        name = extract_justice_name(q1)
        office = extract_judicial_office(q1)
        if not name:
            continue
        # Fourth field holds the retention seat (justice name). Not a vacancy election.
        rows.append(
            {
                "state": "CA",
                "contest_key": contest_key(office, None, name),
                "office": office,
                "district": None,
                "party": "Non-Partisan",
                "candidate_name": name,
                "ballot_designation": None,
                "list_kind": "general_certified_pdf",
                "source_url": PDF_URL,
                "retrieved_at": RETRIEVED,
            }
        )
    return rows


def extract_justice_name(q: str) -> str | None:
    q = re.sub(r"\s+", " ", q)
    if re.search(r"Shall DAVID B\. SAPP be elected", q, re.I):
        return "DAVID B. SAPP"
    m = re.search(
        r"Shall (?:Associate Justice of the Supreme Court|"
        r"Administrative Presiding Justice|"
        r"Presiding Justice|"
        r"Associate Justice|"
        r"San Diego County Superior Court Judge|"
        r"Superior Court Judge)\s+(.+?)\s+be elected",
        q,
        re.I,
    )
    if m:
        return clean_name(m.group(1))
    m = re.search(r"Shall\s+(.+?)\s+be elected", q, re.I)
    if not m:
        return None
    rest = m.group(1)
    rest = re.sub(
        r"^(Associate Justice of the Supreme Court|Administrative Presiding Justice|"
        r"Presiding Justice|Associate Justice|San Diego County Superior Court Judge|"
        r"Superior Court Judge)\s+",
        "",
        rest,
        flags=re.I,
    )
    return clean_name(rest) or None


def extract_judicial_office(q: str) -> str:
    q = re.sub(r"\s+", " ", q)
    if "Supreme Court" in q:
        return "Associate Justice of the Supreme Court"
    if "Administrative Presiding Justice" in q:
        return "Administrative Presiding Justice, Court of Appeal"
    if "Presiding Justice" in q:
        return "Presiding Justice, Court of Appeal"
    if "Superior Court Judge" in q:
        return "Associate Justice, Court of Appeal"
    return "Associate Justice, Court of Appeal"


def summary(rows: list[dict]) -> dict:
    keys = {r["contest_key"] for r in rows}
    house = [r for r in rows if r["office"] == "United States Representative"]
    senate = [r for r in rows if r["office"] in {"State Senate", "State Senator"}]
    assembly = [r for r in rows if r["office"] == "State Assembly Member"]
    judicial = [
        r
        for r in rows
        if "Justice" in (r["office"] or "") or "Court of Appeal" in (r["office"] or "") or "Supreme Court" in (r["office"] or "")
    ]
    us_senate = [r for r in rows if "United States Senate" in (r["office"] or "") or "U.S. Senate" in (r["contest_key"] or "")]
    house_dists = sorted({int(r["district"]) for r in house if r.get("district")})
    return {
        "row_count": len(rows),
        "contest_key_count": len(keys),
        "us_house": len(house),
        "us_house_districts": house_dists,
        "state_senate": len(senate),
        "state_assembly": len(assembly),
        "judicial": len(judicial),
        "us_senate": len(us_senate),
        "source_url": PDF_URL,
        "retrieved_at": RETRIEVED,
        "list_kind": "general_certified_pdf",
    }


def merge_ca_stub(retrieved_votes: str | None = None) -> None:
    if STUB.exists():
        stub = json.loads(STUB.read_text(encoding="utf-8"))
    else:
        stub = {"election": {}, "state_filings": {}, "nominees": {}, "geo_by_zip": {}, "sources": []}
    stub["election"] = {
        "jurisdiction": "California",
        "state_code": "CA",
        "general_date": "2026-11-03",
        "note": "Official SOS certified list of candidates plus Clerk/LIS federal votes. Donors pending Cal-Access.",
    }
    stub["candidates_path"] = "/data/ca/candidates.json"
    stub["candidate_summary_path"] = "/data/ca/candidate-summary.json"
    stub["votes_path"] = stub.get("votes_path") or "/data/ca/votes.json"
    filings = stub.get("state_filings") if isinstance(stub.get("state_filings"), dict) else {}
    if "donors" not in filings:
        filings["donors"] = {
            "status": "pending",
            "reason": "Cal-Access extract not in this populate. Donor names are not invented.",
            "cal_access": "https://cal-access.sos.ca.gov/",
        }
    stub["state_filings"] = filings
    sources = stub.get("sources") or []
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    if PDF_URL not in have:
        sources.append({"url": PDF_URL, "retrieved_at": RETRIEVED})
    stub["sources"] = sources
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    text = fetch_official_text()
    partisan = parse_partisan(text)
    judicial = parse_judicial(text)
    rows = partisan + judicial
    summ = summary(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "candidate-summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    merge_ca_stub()
    print(json.dumps(summ, indent=2))
    ok = (
        summ["row_count"] == 388
        and summ["contest_key_count"] == 228
        and summ["us_house"] == 104
        and summ["state_senate"] == 40
        and summ["state_assembly"] == 156
        and summ["judicial"] == 64
        and summ["us_senate"] == 0
        and summ["us_house_districts"] == list(range(1, 53))
    )
    if not ok:
        print("QA MISMATCH", flush=True)
        by_off = Counter(r["office"] for r in rows)
        print(by_off)
        return 1
    print("QA OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
