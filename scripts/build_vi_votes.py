#!/usr/bin/env python3
"""USVI federal-only Clerk EVS votes for Delegate Plaskett (complete=false).

No U.S. Senate (no seat). Territorial legislature votes are not invented.
Does not rewrite candidates.json or fec-donors.json.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-03T13:54:09Z"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "vi"
STUB = ROOT / "public" / "data" / "vi.json"
CACHE = Path("/tmp/votes-ca-wa/house")
FALLBACK = Path("/tmp/vi-votes/house")
MEMBERDATA = Path("/tmp/votes-wave2/MemberData.xml")
MEMBERDATA_URL = "https://clerk.house.gov/xml/lists/MemberData.xml"
HOUSE_ROLLS = range(253, 293)
BIO = "P000610"
EXPECT = 19
PRESERVE = {
    "public/data/vi/candidates.json": "dc286c85135f544b16a7a93022d18514952b0128",
    "public/data/vi/fec-donors.json": "728458397463c7b624fe2b06af67b9f3dc061e8e",
}


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def assert_preserved() -> None:
    for rel, digest in PRESERVE.items():
        got = sha1(ROOT / rel)
        if got != digest:
            raise SystemExit(f"refusing to wipe {rel}: {digest} -> {got}")


def fetch(url: str, dest: Path, retries: int = 4) -> bytes:
    if dest.exists() and dest.stat().st_size > 200:
        return dest.read_bytes()
    last = None
    dest.parent.mkdir(parents=True, exist_ok=True)
    for i in range(retries):
        req = urllib.request.Request(
            url,
            headers={"User-Agent": UA, "Accept": "application/xml,text/xml,*/*;q=0.8"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            dest.write_bytes(data)
            return data
        except Exception as exc:
            last = exc
            time.sleep(0.5 * (2**i))
    raise RuntimeError(f"fetch failed {url}: {last}")


def house_xml(num: int) -> Path:
    cached = CACHE / f"roll{num}.xml"
    if cached.exists() and cached.stat().st_size > 200:
        return cached
    dest = FALLBACK / f"roll{num}.xml"
    fetch(f"https://clerk.house.gov/evs/2026/roll{num}.xml", dest)
    return dest


def load_plaskett() -> tuple[str, str]:
    raw = MEMBERDATA.read_bytes() if MEMBERDATA.exists() else fetch(MEMBERDATA_URL, Path("/tmp/vi-votes/MemberData.xml"))
    root = ET.fromstring(raw)
    for mem in root.findall(".//member"):
        info = mem.find("member-info")
        if info is None:
            continue
        if (info.findtext("bioguideID") or "").strip() != BIO:
            continue
        name = (info.findtext("official-name") or "").strip()
        statedist = (mem.findtext("statedistrict") or "").strip()
        if statedist != "VI00" or not name:
            raise SystemExit(f"unexpected Clerk MemberData for Plaskett: {statedist} {name}")
        return name, "VI-00"
    raise SystemExit("Clerk MemberData missing sitting Delegate Stacey E. Plaskett")


def house_tally(meta: ET.Element) -> str:
    tot = meta.find(".//totals-by-vote")
    if tot is None:
        return ""
    y = tot.findtext("yea-total") or "0"
    n = tot.findtext("nay-total") or "0"
    p = tot.findtext("present-total") or "0"
    nv = tot.findtext("not-voting-total") or "0"
    return f"Yeas {y}, Nays {n}, Present {p}, Not Voting {nv}"


def parse_house(name: str, dist: str) -> list[dict]:
    rows: list[dict] = []
    for num in HOUSE_ROLLS:
        url = f"https://clerk.house.gov/evs/2026/roll{num}.xml"
        root = ET.fromstring(house_xml(num).read_bytes())
        meta = root.find("vote-metadata")
        if meta is None:
            raise RuntimeError(f"missing vote-metadata {url}")
        base = {
            "chamber": "House",
            "congress": int(meta.findtext("congress") or 119),
            "session": (meta.findtext("session") or "").strip(),
            "roll_call_number": int(meta.findtext("rollcall-num") or num),
            "vote_date": (meta.findtext("action-date") or "").strip(),
            "question": (meta.findtext("vote-question") or "").strip(),
            "measure": (meta.findtext("legis-num") or "").strip(),
            "vote_desc": (meta.findtext("vote-desc") or "").strip(),
            "result": (meta.findtext("vote-result") or "").strip(),
            "tally": house_tally(meta),
            "source_url": url,
            "source_name": "U.S. House Clerk EVS XML",
        }
        for rec in root.findall(".//recorded-vote"):
            leg = rec.find("legislator")
            if leg is None:
                continue
            if (leg.attrib.get("name-id") or "").strip() != BIO:
                continue
            cast = (rec.findtext("vote") or "").strip()
            if not cast:
                raise SystemExit(f"roll {num} missing official vote_cast for {BIO}")
            rows.append(
                {
                    **base,
                    "state": "VI",
                    "incumbent_name": name,
                    "bioguide_id": BIO,
                    "district": dist,
                    "vote_cast": cast,
                    "retrieved_at": RETRIEVED,
                }
            )
    if any(r.get("chamber") == "Senate" for r in rows):
        raise SystemExit("VI votes must not invent Senate rows")
    if len(rows) != EXPECT:
        raise SystemExit(f"VI Plaskett recorded votes {len(rows)} != {EXPECT} in Clerk rolls 253-292")
    return rows


def merge_stub(count: int) -> None:
    stub = json.loads(STUB.read_text(encoding="utf-8"))
    if stub.get("candidates_path") != "/data/vi/candidates.json":
        raise SystemExit("refusing to merge: candidates_path missing")
    if ((stub.get("state_filings") or {}).get("donors") or {}).get("path") != "/data/vi/fec-donors.json":
        raise SystemExit("refusing to merge: fec-donors path missing")
    election = stub.setdefault("election", {})
    election["prefer_for_november"] = "official_august"
    election["no_us_senate"] = True
    election["federal_offices"] = ["Delegate to Congress"]
    election["primary_certified"] = "2026-08-25"
    election["primary_certification_source"] = "https://vivote.gov/2026-primary-election-certification/"
    election["note"] = (
        "Official Election System of the Virgin Islands June candidate listings (88 rows) plus "
        "August general listing (70 rows) and FEC 2026 Delegate master (8 rows). "
        "Primary results were certified August 25, 2026 (VIVOTE Special Notice) — not June 17. "
        "Federal FEC Schedule A $200+ is partial (9 as-filed H/S rows, 4 with receipts, 326 kept). "
        "Federal Clerk EVS votes are partial (Delegate only, complete=false). "
        "Prefer August general for November. No U.S. Senate. Territorial campaign-finance bulk "
        "is pending. Streets omitted. Donor lists are not sold."
    )
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings.setdefault("state_donors", {})["status"] = "pending"
    stub["votes_path"] = "/data/vi/votes.json"
    stub["docs"] = {
        "source_meta": "/data/vi/SOURCE_META.json",
        "notes": "/data/vi/NOTES.md",
        "schema": "/data/vi/SCHEMA.md",
        "discovery": "/data/vi/DISCOVERY.md",
    }
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {
            "url": "https://vivote.gov/2026-primary-election-certification/",
            "retrieved_at": RETRIEVED,
            "note": "Official VIVOTE Special Notice: 2026 Primary Election certified August 25, 2026 (not June 17)",
        },
        {
            "url": "https://clerk.house.gov/evs/2026/index.asp",
            "retrieved_at": RETRIEVED,
            "note": "House Clerk EVS 2026 — Delegate Plaskett federal-only (complete=false)",
        },
        {"url": MEMBERDATA_URL, "retrieved_at": RETRIEVED, "note": "Clerk MemberData sitting House members"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    votes_block = filings.setdefault("votes", {})
    votes_block.update(
        {
            "status": "partial",
            "path": "/data/vi/votes.json",
            "complete": False,
            "federal_only": True,
            "no_us_senate": True,
            "retrieved_at": RETRIEVED,
            "source_url": "https://clerk.house.gov/evs/2026/index.asp",
            "counts": {"rows": count, "members": 1, "house_rolls_with_delegate": count},
        }
    )
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    assert_preserved()
    name, dist = load_plaskett()
    rows = parse_house(name, dist)
    rows = sorted(rows, key=lambda r: -(r.get("roll_call_number") or 0))
    payload = {
        "policy": (
            "Official U.S. House Clerk EVS XML (2026 unpadded rolls 253-292) for the sitting "
            "U.S. Virgin Islands Delegate. House match is name-id==bioguide from Clerk "
            "MemberData.xml. The Delegate is recorded only on some amendment/Committee of "
            "the Whole rolls; other floor rolls have no official Delegate recorded-vote and "
            "are not invented. There is no U.S. Senate seat. Territorial legislature votes "
            "are not extracted (complete=false, federal_only). vote_cast is the exact official "
            "text. No Ballotpedia. No scores."
        ),
        "retrieved_at": RETRIEVED,
        "source_url": "https://clerk.house.gov/evs/2026/index.asp",
        "state": "VI",
        "count": len(rows),
        "complete": False,
        "federal_only": True,
        "no_us_senate": True,
        "no_us_senate_contest": True,
        "office": "Delegate to Congress",
        "member_bioguide": BIO,
        "district": dist,
        "counts_by_member": dict(sorted(Counter(r["bioguide_id"] for r in rows).items())),
        "votes": rows,
        "method": {
            "house": {
                "source": "https://clerk.house.gov/evs/2026/index.asp",
                "rolls": "253-292",
                "url_pattern": "https://clerk.house.gov/evs/2026/roll{N}.xml",
                "match": "legislator name-id == Clerk MemberData bioguideID",
                "memberdata": MEMBERDATA_URL,
                "delegate_recorded_rolls": sorted({r["roll_call_number"] for r in rows}),
            },
            "senate": {
                "skipped": True,
                "reason": "U.S. Virgin Islands has no U.S. Senate seat. Senate LIS rows are not invented.",
            },
            "skip": [
                "Territorial Legislature of the Virgin Islands floor votes are not in this federal-only extract",
                "House floor rolls 253-292 with no official Delegate recorded-vote are omitted (not invented)",
            ],
            "user_agent": UA,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "votes.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    merge_stub(len(rows))
    assert_preserved()
    print(f"wrote VI votes {len(rows)} Plaskett {name} federal_only complete=false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
