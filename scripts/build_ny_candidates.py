#!/usr/bin/env python3
"""Official NYSBOE 2026 general ballot certification (amended Sep 4, 2026)."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-09T18:05:36Z"
CERT_DATE = "2026-09-04"
LANDING = "https://elections.ny.gov/ballot-certifications-elections"
CERT_PAGE = "https://elections.ny.gov/certification-november-3-2026-general-election"
WHO_FILED = "https://publicreporting.elections.ny.gov/WhoFiled/WhoFiled"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "ny"
STUB = ROOT / "public" / "data" / "ny.json"
ORIGIN = Path("/workspace/wtp-live-data/50state/2026-09-09-ny-cert/NY/package")
CACHE = Path("/tmp/ny-cert")
EXPECT_ROWS = 849
EXPECT_KEYS = 254
STREET_KEYS = {"street", "address", "addr", "mailing_address", "email", "phone", "zip", "zipcode"}

MAJOR_PARTIES = {
    "Democratic",
    "Republican",
    "Conservative",
    "Working Families",
    "Libertarian",
    "Reform",
    "Independence",
    "Green",
    "Vote Affordable",
    "Voter Options",
}
INDEPENDENT_BODIES = {
    "4 Our Immigrants",
    "Affordable & Safe",
    "Arts & Culture",
    "Block Mamdani",
    "Coalition",
    "Common Sense",
    "Community First",
    "FGT AntiSemitism",
    "For All of Us",
    "Mercedes Simmons Cares",
    "Mohawk Valley 1st",
    "No Kings",
    "Our Future",
    "People First",
    "People Over Politics",
    "Queens United",
    "Save NYC",
    "Socialism PSL",
    "Speak The Truth",
    "Stop Mamdani",
    "Taxpayer Rights",
    "The Answer",
    "We The People",
}
PARTIES = MAJOR_PARTIES | INDEPENDENT_BODIES
SKIP = {
    "Party Candidate Name",
    "Party Governor",
    "Candidate Name",
    "Lt. Governor Candidate Name",
    "Litigation Pending",
}
COUNTY_LINE = re.compile(
    r"^(Counties:|Counties |Part of |All$|New York$|Kings$|Queens$|Bronx$|Richmond$"
    r"|Warren,|Schenectady,|Genesee,|Livingston,)"
)


def is_party(token: str) -> bool:
    return token in PARTIES


def is_meta(token: str) -> bool:
    return (
        token.startswith("Office:")
        or token.startswith("District:")
        or token.startswith("Counties:")
        or token.startswith("Counties ")
        or token.startswith("Vote For:")
        or token.startswith("Party ")
        or token in SKIP
        or token.startswith("Part of ")
        or bool(COUNTY_LINE.match(token))
        or ("," in token and "Part of " in token)
        or ("," in token and "&" in token and not re.search(r"[A-Z]\.", token))
    )


def district_value(raw: str | None) -> str | None:
    if not raw or raw.lower() == "statewide":
        return None
    return raw


def contest_key(office: str, district: str | None) -> str:
    return f"NY|{office}|{district or ''}|"


def load_cert_text() -> str:
    origin_txt = ORIGIN / "cert.txt"
    if origin_txt.exists():
        return origin_txt.read_text(encoding="utf-8", errors="replace")
    cached = CACHE / "cert.txt"
    if cached.exists() and cached.stat().st_size > 1000:
        return cached.read_text(encoding="utf-8", errors="replace")
    raise SystemExit(
        f"missing official NYSBOE general certification text ({cached} or {origin_txt}); "
        f"do not invent names. Official page: {CERT_PAGE}"
    )


def parse_rows(text: str) -> list[dict]:
    text = text.replace("SteOffice:", "Office:")
    lines = [ln.strip() for ln in text.splitlines()]
    starts = [i for i, ln in enumerate(lines) if ln.startswith("Office:")]
    if not starts:
        raise SystemExit("certification text has no Office: blocks")
    rows: list[dict] = []
    seen: set[tuple] = set()

    def emit(office: str, district: str | None, party: str, name: str, litigation: bool) -> None:
        name = (name or "").strip()
        if not name or is_party(name) or is_meta(name):
            return
        dist = district_value(district)
        key = (office, dist, party, name)
        if key in seen:
            return
        seen.add(key)
        rec = {
            "state": "NY",
            "contest_key": contest_key(office, dist),
            "office": office,
            "district": dist,
            "candidate_office": office,
            "party": party,
            "candidate_name": name,
            "list_kind": "general_ballot_certification",
            "election": "2026 General Election",
            "election_year": "2026",
            "election_date": "2026-11-03",
            "certification_date": CERT_DATE,
            "complete": True,
            "source_url": CERT_PAGE,
            "retrieved_at": RETRIEVED,
        }
        if litigation:
            rec["candidate_status"] = "Litigation Pending"
        if STREET_KEYS & {k.lower() for k in rec}:
            raise SystemExit("street field leaked into NY certification row")
        rows.append(rec)

    for bi, start in enumerate(starts):
        end = starts[bi + 1] if bi + 1 < len(starts) else len(lines)
        block = [ln for ln in lines[start:end] if ln]
        office = block[0].split(":", 1)[1].strip()
        district = None
        vote_for = 1
        litigation = False
        body: list[str] = []
        for ln in block[1:]:
            if ln.startswith("District:"):
                district = ln.split(":", 1)[1].strip()
            elif ln.startswith("Vote For:"):
                vote_for = int(re.search(r"\d+", ln).group())
            elif ln == "Litigation Pending":
                litigation = True
            elif is_meta(ln):
                continue
            elif ln.startswith("Democratic ") and not is_party(ln):
                body.extend(["Democratic", ln[len("Democratic ") :].strip()])
            else:
                body.append(ln)

        groups: list[tuple[str, list[str]]] = []
        j = 0
        while j < len(body):
            if is_party(body[j]):
                party = body[j]
                j += 1
                names: list[str] = []
                while j < len(body) and not is_party(body[j]):
                    names.append(body[j])
                    j += 1
                groups.append((party, names))
            else:
                j += 1

        if office == "Governor and Lt. Governor":
            for party, names in groups:
                if names:
                    emit("Governor", district, party, names[0], litigation)
                if len(names) > 1:
                    emit("Lt. Governor", district, party, names[1], litigation)
            continue

        if vote_for == 1:
            repaired: list[tuple[str, list[str]]] = []
            g = 0
            while g < len(groups):
                party, names = groups[g]
                if (
                    not names
                    and g + 1 < len(groups)
                    and len(groups[g + 1][1]) >= 2
                    and party in MAJOR_PARTIES
                ):
                    nxt_party, nxt_names = groups[g + 1]
                    repaired.append((party, [nxt_names[0]]))
                    repaired.append((nxt_party, nxt_names[1:]))
                    g += 2
                    continue
                repaired.append((party, names))
                g += 1
            groups = repaired

        for party, names in groups:
            for name in names:
                emit(office, district, party, name, litigation)

    return rows


def origin_rows() -> list[dict] | None:
    path = ORIGIN / "candidates.json"
    if not path.exists():
        return None
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("origin NY package candidates.json is not a list")
    return rows


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
    stub["election"] = {
        "jurisdiction": "New York",
        "state_code": "NY",
        "general_date": "2026-11-03",
        "note": (
            "Official NYSBOE amended general ballot certification dated September 4, 2026 "
            "(November 3, 2026 General Election; preferred over Who Filed), NYSBOE Schedule A–D "
            "donors (Open NY e9ss-239a), Clerk/LIS federal votes, and federal FEC Schedule A $200+. "
            "Donor lists are not sold."
        ),
    }
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["donors"] = donors
    filings["federal_fec"] = fec
    filings["who_filed"] = WHO_FILED
    filings["nysboe_cert"] = CERT_PAGE
    filings["nysboe_cert_landing"] = LANDING
    filings["candidates"] = {
        "status": "sourced",
        "path": "/data/ny/candidates.json",
        "source_url": CERT_PAGE,
        "landing_url": LANDING,
        "retrieved_at": RETRIEVED,
        "certification_date": CERT_DATE,
        "complete": True,
        "certified": True,
        "prefer_for_november": "general_ballot_certification",
        "counts": {
            "rows": len(rows),
            "contest_keys": len({r["contest_key"] for r in rows}),
            "general_ballot_certification": len(rows),
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
    extra = [
        {
            "url": CERT_PAGE,
            "retrieved_at": RETRIEVED,
            "note": "Official NYSBOE amended Nov 3 2026 general ballot certification (dated Sep 4, 2026)",
        },
        {
            "url": LANDING,
            "retrieved_at": RETRIEVED,
            "note": "NYSBOE ballot certifications landing",
        },
    ]
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    for src in extra:
        if src["url"] in have:
            for existing in sources:
                if existing.get("url") == src["url"]:
                    existing["retrieved_at"] = src["retrieved_at"]
                    existing["note"] = src["note"]
        else:
            sources.append(src)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    rows = origin_rows()
    if rows is None:
        rows = parse_rows(load_cert_text())
    if len(rows) != EXPECT_ROWS:
        raise SystemExit(f"NY certified rows {len(rows)} != {EXPECT_ROWS}")
    kinds = Counter(r.get("list_kind") for r in rows)
    if kinds.get("general_ballot_certification") != EXPECT_ROWS:
        raise SystemExit(f"NY list_kind {dict(kinds)} != general_ballot_certification/{EXPECT_ROWS}")
    keys = {r["contest_key"] for r in rows}
    if len(keys) != EXPECT_KEYS:
        raise SystemExit(f"NY contest_keys {len(keys)} != {EXPECT_KEYS}")
    if any(str(k).count("|") != 3 or not str(k).startswith("NY|") for k in keys):
        raise SystemExit("NY contest_key must be NY|OFFICE|DIST|")
    if any(r.get("complete") is not True for r in rows):
        raise SystemExit("NY certified rows must be complete=true")
    if any(r.get("retrieved_at") != RETRIEVED for r in rows):
        raise SystemExit(f"NY retrieved_at must be {RETRIEVED}")
    if any("ballotpedia" in (r.get("source_url") or "").lower() for r in rows):
        raise SystemExit("NY candidates must not use Ballotpedia")
    if not any(r.get("candidate_name") == "Kathy C. Hochul" for r in rows):
        raise SystemExit("NY cert missing Kathy C. Hochul")
    if not any(r.get("candidate_name") == "George S. Latimer" for r in rows):
        raise SystemExit("NY cert missing George S. Latimer")
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
        "list_kind": "general_ballot_certification",
        "by_list_kind": dict(kinds),
        "by_party": dict(Counter(r["party"] for r in rows)),
        "by_office": dict(Counter(r["office"] for r in rows)),
        "complete": True,
        "certified": True,
        "prefer_for_november": "general_ballot_certification",
        "certification_date": CERT_DATE,
        "source_url": CERT_PAGE,
        "landing_url": LANDING,
        "retrieved_at": RETRIEVED,
        "streets_omitted": True,
        "note": (
            "Official NYSBOE amended Certification for the November 3, 2026 General Election "
            "(dated September 4, 2026; retrieved 2026-09-09T18:05:36Z). Replaces Who Filed as "
            "the preferred November list. 849 general_ballot_certification rows / 254 contest keys / "
            "complete=true. One row per certified name + party line. Governor and Lt. Governor are "
            "separate keys. Streets omitted. No Ballotpedia."
        ),
        "user_agent": UA,
    }
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub(rows)
    print(f"wrote NY certified {len(rows)} keys={len(keys)} complete=true", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
