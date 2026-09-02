#!/usr/bin/env python3
"""Parse official Arizona SOS 2026 primary nominations/petitions-filed PDF."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T11:23:07Z"
PDF_URL = "https://azsos.gov/sites/default/files/docs/2026-Candidate-Nominations-and-Petitions-Filed-0330.pdf"
WAYBACK_URL = (
    "https://web.archive.org/web/20260621034222id_/"
    "https://azsos.gov/sites/default/files/docs/2026-Candidate-Nominations-and-Petitions-Filed-0330.pdf"
)
LANDING_URL = "https://azsos.gov/media/666"
LIST_KIND = "primary_nominations_petitions_filed"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "az"
STUB = ROOT / "public" / "data" / "az.json"
CACHE = Path("/tmp/az-sos")
PDF_NAME = "2026-Candidate-Nominations-and-Petitions-Filed-0330.pdf"

PARTIES = (
    "Arizona Independent Party",
    "Democratic",
    "Republican",
    "Libertarian",
    "Independent",
    "Green",
)
OFFICES = (
    r"U\.S\. Representative - District No\. \d+",
    r"State Senator - District No\. \d+",
    r"State Representative - District No\. \d+",
    r"Superintendent of Public Instruction",
    r"Corporation Commissioner",
    r"Secretary of State",
    r"Attorney General",
    r"State Treasurer",
    r"State Mine Inspector",
    r"Governor",
)
SKIP = re.compile(
    r"^(Arizona Secretary of State|Partisan Candidate Filing|February 23|"
    r"Candidate Name|Official list of candidates|Page \d+|"
    r"Title:|Subject:|Keywords:|Author:|Creator:|Producer:|"
    r"CreationDate:|ModDate:|Custom Metadata|Metadata Stream)",
    re.I,
)
LINE_RE = re.compile(
    r"^(\S.*?\S)\s{2,}(" + "|".join(OFFICES) + r")\s{2,}(" + "|".join(re.escape(p) for p in PARTIES) + r")\b"
    r"\s+(\d+)?\s+([A-Za-z]+ \d+, \d+)?"
)
DIST_RE = re.compile(r"^(.*?)(?:\s*-\s*District No\. (\d+))?$")


def contest_key(office: str, district: str | None) -> str:
    return f"AZ|{office}|{district or ''}|"


def split_contest(contest: str) -> tuple[str, str | None]:
    m = DIST_RE.match(contest)
    if not m:
        return contest, None
    office = (m.group(1) or contest).strip()
    dist = m.group(2)
    return office, dist


def fetch_pdf() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / PDF_NAME
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest
    for url in (PDF_URL, WAYBACK_URL):
        try:
            subprocess.check_call(
                ["curl", "-fsSL", "-A", UA, "--max-time", "90", "-o", str(dest), url]
            )
            if dest.exists() and dest.stat().st_size > 10_000:
                return dest
        except subprocess.CalledProcessError:
            continue
    raise SystemExit("could not retrieve official AZ SOS nominations PDF")


def pdf_text(pdf: Path) -> str:
    txt = CACHE / "az.txt"
    subprocess.check_call(["pdftotext", "-layout", str(pdf), str(txt)])
    return txt.read_text(encoding="utf-8", errors="replace")


def parse_rows(text: str) -> list[dict]:
    out: list[dict] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or SKIP.search(line.strip()):
            continue
        m = LINE_RE.search(line)
        if not m:
            continue
        name = m.group(1).strip()
        contest = m.group(2).strip()
        party = m.group(3).strip()
        filed = (m.group(5) or "").strip() or None
        office, district = split_contest(contest)
        if not name or not office:
            raise SystemExit(f"missing filed name/office: {line!r}")
        out.append(
            {
                "state": "AZ",
                "contest_key": contest_key(office, district),
                "office": office,
                "district": district,
                "candidate_office": contest,
                "party": party,
                "candidate_name": name,
                "list_kind": LIST_KIND,
                "election": "2026 Primary Election",
                "election_year": "2026",
                "filing_window": "February 23, 2026, to March 23, 2026",
                "filing_date": filed,
                "source_url": PDF_URL,
                "retrieved_at": RETRIEVED,
            }
        )
    return out


def summarize(rows: list[dict]) -> dict:
    keys = {r["contest_key"] for r in rows}
    house = [r for r in rows if r["office"] == "U.S. Representative"]
    return {
        "row_count": len(rows),
        "contest_key_count": len(keys),
        "list_kind": LIST_KIND,
        "us_house": len(house),
        "us_house_districts": sorted({int(r["district"]) for r in house if str(r.get("district") or "").isdigit()}),
        "governor": sum(1 for r in rows if r["office"] == "Governor"),
        "state_senate": sum(1 for r in rows if r["office"] == "State Senator"),
        "state_house": sum(1 for r in rows if r["office"] == "State Representative"),
        "by_office": dict(Counter(r["office"] for r in rows)),
        "by_party": dict(Counter(r["party"] for r in rows)),
        "source_url": PDF_URL,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official Arizona SOS Partisan Candidate Filing PDF for the 2026 primary "
            "(nominations and petitions filed, February 23–March 23, 2026). "
            "This is NOT a November general certified roster. "
            "apps.arizona.vote general list is Cloudflare-blocked with no free bulk. "
            "Names as filed only. list_kind kept. Streets omitted. No Ballotpedia."
        ),
    }


def write_stub() -> None:
    if STUB.exists():
        stub = json.loads(STUB.read_text(encoding="utf-8"))
    else:
        stub = {}
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    stub["election"] = {
        "jurisdiction": "Arizona",
        "state_code": "AZ",
        "general_date": None,
        "note": (
            "Official SOS 2026 primary nominations/petitions-filed PDF and Clerk/LIS federal votes. "
            "This is not a November general certified roster; apps.arizona.vote is Cloudflare-blocked. "
            "State campaign-finance bulk is blocked ($25 PRR / SeeTheMoney). Donor lists are not sold."
        ),
    }
    stub["state_filings"] = {
        "wired": True,
        "azsos_public": "https://azsos.gov/elections/candidates",
        "azsos_nominations_pdf": PDF_URL,
        "donors": donors
        or {
            "status": "pending",
            "reason": "State campaign-finance bulk is blocked ($25 PRR / SeeTheMoney). Donor names are not invented.",
            "do_not_sell_donor_lists": True,
        },
    }
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    stub["candidates_path"] = "/data/az/candidates.json"
    stub["candidate_summary_path"] = "/data/az/candidate-summary.json"
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {
            "url": PDF_URL,
            "retrieved_at": RETRIEVED,
            "note": "AZ SOS 2026 primary nominations/petitions filed PDF (not general certified)",
        },
        {
            "url": LANDING_URL,
            "retrieved_at": RETRIEVED,
            "note": "AZ SOS media landing for the nominations PDF",
        },
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    STUB.parent.mkdir(parents=True, exist_ok=True)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote stub", STUB, flush=True)


def main() -> int:
    pdf = fetch_pdf()
    rows = parse_rows(pdf_text(pdf))
    if len(rows) != 266:
        raise SystemExit(f"expected 266 official filing rows, got {len(rows)}")
    keys = {r["contest_key"] for r in rows}
    if len(keys) != 76:
        raise SystemExit(f"expected 76 contest_keys, got {len(keys)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summarize(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub()
    print(f"wrote {len(rows)} candidates, contest_keys={len(keys)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
