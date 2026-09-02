#!/usr/bin/env python3
"""Official Florida DOS 2026 general candidate extracts (state + local)."""

from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from collections import Counter
from http.cookiejar import CookieJar
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T12:56:25Z"
ELEC_ID = "20261103-GEN"
LANDING_URL = "https://dos.elections.myflorida.com/candidates/downloadcanlist.asp"
EXTRACT_URL = "https://dos.elections.myflorida.com/candidates/extractCanList.asp"
STA_SOURCE = f"{EXTRACT_URL}?elecID={ELEC_ID}&canType=STA"
LOC_SOURCE = f"{EXTRACT_URL}?elecID={ELEC_ID}&canType=LOC"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "fl"
STUB = ROOT / "public" / "data" / "fl.json"
CACHE = Path("/tmp/fl-dos")
EXPECTED = {"STA": 1145, "LOC": 2656}

# Official extract columns that are streets / PII — never copy into JSON.
OMIT = {
    "VoterID",
    "SuppressAddress",
    "Addr1",
    "Addr2",
    "City",
    "State",
    "Zip",
    "Phone",
    "TrsNameLast",
    "TrsNameFirst",
    "TrsNameMiddle",
    "Email",
}


def contest_key(office: str, district: str | None) -> str:
    return f"FL|{office}|{district or ''}|"


def filed_name(first: str, middle: str, last: str) -> str:
    return " ".join(p for p in (first, middle, last) if p)


def filed_district(juris1: str, juris2: str) -> str | None:
    if juris1 and juris2:
        return f"{juris1}-{juris2}"
    return juris1 or juris2 or None


def decode_extract(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def fetch_extract(can_type: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"{can_type}.bin"
    expected = EXPECTED[can_type]
    if dest.exists():
        text = decode_extract(dest.read_bytes())
        n = max(0, len(text.splitlines()) - 1)
        if n == expected:
            return dest
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    landing = urllib.request.Request(
        LANDING_URL,
        headers={"User-Agent": UA, "Accept": "text/html,*/*"},
    )
    with opener.open(landing, timeout=90) as resp:
        resp.read()
    body = urllib.parse.urlencode(
        {
            "elecID": ELEC_ID,
            "office": "All",
            "status": "All",
            "cantype": can_type,
            "FormSubmit": "Download Candidate List",
        }
    ).encode()
    req = urllib.request.Request(
        EXTRACT_URL,
        data=body,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": LANDING_URL,
            "Origin": "https://dos.elections.myflorida.com",
        },
        method="POST",
    )
    with opener.open(req, timeout=180) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return dest


def parse_extract(path: Path, can_type: str) -> list[dict]:
    list_kind = "state_extract" if can_type == "STA" else "local_extract"
    source_url = STA_SOURCE if can_type == "STA" else LOC_SOURCE
    text = decode_extract(path.read_bytes())
    reader = csv.DictReader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
    rows: list[dict] = []
    for rec in reader:
        office = (rec.get("OfficeDesc") or "").strip()
        first = (rec.get("NameFirst") or "").strip()
        middle = (rec.get("NameMiddle") or "").strip()
        last = (rec.get("NameLast") or "").strip()
        name = filed_name(first, middle, last)
        if not office or not name:
            raise SystemExit(f"missing filed name/office in {can_type}: {rec!r}")
        if OMIT & rec.keys() and any((rec.get(k) or "").strip() for k in OMIT):
            pass  # omitted below; presence on the official row is expected
        j1 = (rec.get("Juris1num") or "").strip()
        j2 = (rec.get("Juris2num") or "").strip()
        district = filed_district(j1, j2)
        party = (rec.get("PartyDesc") or "").strip() or None
        status = (rec.get("StatusDesc") or "").strip() or None
        county = (rec.get("County") or "").strip() or None
        candidate_office = f"{office}, {district}" if district else office
        rows.append(
            {
                "state": "FL",
                "contest_key": contest_key(office, district),
                "office": office,
                "district": district,
                "candidate_office": candidate_office,
                "party": party,
                "candidate_name": name,
                "list_kind": list_kind,
                "election": "2026 General Election",
                "election_year": "2026",
                "election_id": (rec.get("ElectionID") or ELEC_ID).strip(),
                "acct_num": (rec.get("AcctNum") or "").strip() or None,
                "office_code": (rec.get("OfficeCode") or "").strip() or None,
                "status_code": (rec.get("StatusCode") or "").strip() or None,
                "status_desc": status,
                "party_code": (rec.get("PartyCode") or "").strip() or None,
                "county": county,
                "juris1num": j1 or None,
                "juris2num": j2 or None,
                "source_url": source_url,
                "retrieved_at": RETRIEVED,
            }
        )
    if len(rows) != EXPECTED[can_type]:
        raise SystemExit(f"expected {EXPECTED[can_type]} {can_type} rows, got {len(rows)}")
    return rows


def summarize(rows: list[dict]) -> dict:
    keys = {r["contest_key"] for r in rows}
    house = [r for r in rows if r["office"] == "United States Representative"]
    senate = [r for r in rows if r["office"] == "United States Senator"]
    gov = [r for r in rows if r["office"] == "Governor"]
    kinds = Counter(r["list_kind"] for r in rows)
    return {
        "row_count": len(rows),
        "contest_key_count": len(keys),
        "state_extract_rows": kinds.get("state_extract", 0),
        "local_extract_rows": kinds.get("local_extract", 0),
        "us_senate": len(senate),
        "us_house": len(house),
        "us_house_districts": sorted(
            {r["district"] for r in house if r.get("district")},
            key=lambda d: (len(d), d),
        ),
        "governor": len(gov),
        "state_senate": sum(1 for r in rows if r["office"] == "State Senator"),
        "state_house": sum(1 for r in rows if r["office"] == "State Representative"),
        "by_list_kind": dict(kinds),
        "by_office": dict(Counter(r["office"] for r in rows)),
        "by_party": dict(Counter((r.get("party") or "") for r in rows)),
        "source_urls": [STA_SOURCE, LOC_SOURCE, LANDING_URL],
        "election_id": ELEC_ID,
        "retrieved_at": RETRIEVED,
        "note": (
            "Official Florida Division of Elections candidate extracts for elecID=20261103-GEN "
            "(2026 Election / general). State (STA) and local (LOC) lists are kept separate via "
            "list_kind state_extract/local_extract. Names are copied from filed NameFirst/"
            "NameMiddle/NameLast only and are never invented. Streets, phone, email, voter id, "
            "and treasurer names are omitted. No Ballotpedia."
        ),
    }


def write_stub() -> None:
    if STUB.exists():
        stub = json.loads(STUB.read_text(encoding="utf-8"))
    else:
        stub = {}
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    stub["election"] = {
        "jurisdiction": "Florida",
        "state_code": "FL",
        "general_date": "2026-11-03",
        "note": (
            "Official Florida DOS 2026 general candidate extracts (state + local), Clerk/LIS "
            "federal votes, and federal FEC Schedule A $200+. State campaign-finance bulk is "
            "blocked (no standing statewide bulk URL; access is form-limited). Donor lists are "
            "not sold."
        ),
    }
    stub["state_filings"] = {
        "wired": True,
        "fl_dos_candidates": LANDING_URL,
        "fl_dos_state_extract": STA_SOURCE,
        "fl_dos_local_extract": LOC_SOURCE,
        "donors": donors
        if donors.get("status") in {"sourced", "partial"}
        else {
            "status": "pending",
            "reason": (
                "Florida has no standing statewide campaign-finance bulk download URL; "
                "Division of Elections campaign-finance access is form-limited. State donor "
                "names are not invented. Federal FEC Schedule A $200+ may land later."
            ),
            "do_not_sell_donor_lists": True,
        },
    }
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    stub["candidates_path"] = "/data/fl/candidates.json"
    stub["candidate_summary_path"] = "/data/fl/candidate-summary.json"
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {
            "url": LANDING_URL,
            "retrieved_at": RETRIEVED,
            "note": "Florida DOS Download Candidate List form (elecID=20261103-GEN)",
        },
        {
            "url": STA_SOURCE,
            "retrieved_at": RETRIEVED,
            "note": "Official STA extract (state candidates)",
        },
        {
            "url": LOC_SOURCE,
            "retrieved_at": RETRIEVED,
            "note": "Official LOC extract (local candidates)",
        },
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    STUB.parent.mkdir(parents=True, exist_ok=True)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote stub", STUB, flush=True)


def main() -> int:
    sta = parse_extract(fetch_extract("STA"), "STA")
    loc = parse_extract(fetch_extract("LOC"), "LOC")
    rows = sta + loc
    if len(rows) != 3801:
        raise SystemExit(f"expected 3801 official filing rows, got {len(rows)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summarize(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub()
    print(
        f"wrote {len(rows)} candidates (STA={len(sta)} LOC={len(loc)}) "
        f"contest_keys={len({r['contest_key'] for r in rows})}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
