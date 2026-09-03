#!/usr/bin/env python3
"""Add official House Clerk EVS rolls 293-295 for Case and Tokuda.

+6 HI House facts (both Nay on all three). congress 218→224.
Does not rewrite Senate LIS (latest 231), Hawaii capitol votes (1241 freeze),
CSC donors, Kitashima empty, or FEC donors. Votes are never invented. No scores.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
CACHE = Path("/tmp/hi-votes")
RETRIEVED = "2026-09-03T18:00:00Z"
ROLLS = [293, 294, 295]
HOUSE = {
    "C001055": {"incumbent_name": "Ed Case", "district": "HI-01"},
    "T000487": {"incumbent_name": "Jill Tokuda", "district": "HI-02"},
}
FROZEN_SHA256 = {
    "csc-donors.json": "224c7ec6e7a1917ae9ba548d12012125deddace8728d3bbf3af1f6269cd84984",
    "donors.json": "0da3ef63f07e81cb9c1f67d685546e06b25c66d1dfd06794e2448e799abd8135",
    "hawaii-votes.json": "0de4d06ca2f8af476efe8f2d16930e8fedf6f9b303f995dab0e78bb318d4369e",
    "hawaii.json": "b37e059d6d7a4bc944e94714499ef39d9b57d1062a3cdc2f72a62faff117606c",
}
PACKAGE_DIRS = [
    Path("/workspace/wtp-votes/run-2026-09-03-hst08"),
    Path("/tmp/wtp-votes/run-2026-09-03-hst08"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_frozen() -> None:
    for name, digest in FROZEN_SHA256.items():
        got = sha256(OUT / name)
        if got != digest:
            raise SystemExit(f"refusing to wipe {name}: {digest} -> {got}")


def fetch_roll(num: int) -> Path:
    dest = CACHE / f"roll{num}.xml"
    if dest.exists() and dest.stat().st_size > 2000:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://clerk.house.gov/evs/2026/roll{num}.xml"
    last = None
    for i in range(4):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "application/xml,text/xml,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if len(data) < 2000:
                raise RuntimeError(f"roll {num} too small ({len(data)})")
            dest.write_bytes(data)
            return dest
        except Exception as exc:
            last = exc
            time.sleep(0.5 * (2**i))
    raise SystemExit(f"fetch failed {url}: {last}")


def parse_roll(num: int) -> tuple[dict, dict[str, str]]:
    root = ET.fromstring(fetch_roll(num).read_bytes())
    meta = root.find("vote-metadata")
    if meta is None:
        raise SystemExit(f"roll {num} missing vote-metadata")
    tot = meta.find(".//totals-by-vote")
    y = (tot.findtext("yea-total") if tot is not None else "") or "0"
    n = (tot.findtext("nay-total") if tot is not None else "") or "0"
    url = f"https://clerk.house.gov/evs/2026/roll{num}.xml"
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
        "tally": f"{y}-{n}",
        "source_url": url,
        "source_name": "U.S. House Clerk EVS XML",
        "retrieved_at": RETRIEVED,
    }
    casts: dict[str, str] = {}
    for rec in root.findall(".//recorded-vote"):
        leg = rec.find("legislator")
        if leg is None:
            continue
        bio = leg.attrib.get("name-id")
        if bio not in HOUSE:
            continue
        cast = (rec.findtext("vote") or "").strip()
        if not cast:
            raise SystemExit(f"roll {num} {bio} missing official vote_cast")
        casts[bio] = cast
    if set(casts) != set(HOUSE):
        raise SystemExit(f"roll {num} missing HI House vote: {casts}")
    if any(casts[bio] != "Nay" for bio in HOUSE):
        raise SystemExit(f"roll {num} expected official Nay for Case and Tokuda, got {casts}")
    return base, casts


def apply_delta(congress: dict) -> dict:
    byc = congress["by_incumbent"]
    for bio, n in {"H001042": 50, "S001194": 50}.items():
        rec = byc[bio]
        if rec.get("item_count_all") != n:
            raise SystemExit(f"{bio} Senate count {rec.get('item_count_all')} != {n}")
        top = (rec.get("items") or [{}])[0]
        if top.get("roll_call_number") != 231:
            raise SystemExit(f"{bio} latest Senate roll {top.get('roll_call_number')} != 231")

    new_rows: list[dict] = []
    for num in ROLLS:
        base, casts = parse_roll(num)
        for bio, info in HOUSE.items():
            new_rows.append(
                {
                    **base,
                    "incumbent_name": info["incumbent_name"],
                    "bioguide_id": bio,
                    "district": info["district"],
                    "vote_cast": casts[bio],
                }
            )

    added = 0
    for bio in HOUSE:
        rec = byc[bio]
        have = {it["roll_call_number"] for it in rec["items"]}
        extras = [row for row in new_rows if row["bioguide_id"] == bio and row["roll_call_number"] not in have]
        rec["items"] = sorted(rec["items"] + extras, key=lambda it: -(it.get("roll_call_number") or 0))
        rec["item_count_all"] = len(rec["items"])
        added += len(extras)
        if rec["item_count_all"] != 62:
            raise SystemExit(f"{bio} expected 62 House votes, got {rec['item_count_all']}")

    if added != 6:
        raise SystemExit(f"expected +6 new House facts (293-295 x2), got {added}")

    tokuda_288 = next((i for i in byc["T000487"]["items"] if i.get("roll_call_number") == 288), None)
    if not tokuda_288 or tokuda_288.get("vote_cast") != "No":
        raise SystemExit(f"Tokuda roll 288 must stay official No, got {tokuda_288}")

    house_votes = []
    case = {it["roll_call_number"]: it for it in byc["C001055"]["items"]}
    tokuda = {it["roll_call_number"]: it for it in byc["T000487"]["items"]}
    for num in sorted(set(case) | set(tokuda), reverse=True):
        if num in case:
            house_votes.append(case[num])
        if num in tokuda:
            house_votes.append(tokuda[num])
    senate_votes = [v for v in congress["votes"] if v.get("chamber") == "Senate"]
    if len(senate_votes) != 100:
        raise SystemExit(f"Senate votes flattened {len(senate_votes)} != 100")
    congress["votes"] = house_votes + senate_votes
    congress["row_count"] = len(congress["votes"])
    if congress["row_count"] != 224:
        raise SystemExit(f"congress row_count {congress['row_count']} != 224")
    congress["retrieved_at"] = RETRIEVED
    congress["policy"] = (
        "Official U.S. House Clerk EVS XML (2026 rolls) and U.S. Senate LIS roll-call XML "
        "for Hawaii incumbents. vote_cast is the exact official text. Votes are never invented. "
        "No Ballotpedia. No scores."
    )
    sources = congress.get("sources") or []
    for src in sources:
        if "clerk.house.gov" in (src.get("url") or ""):
            src["retrieved_at"] = RETRIEVED
            src["note"] = (
                "House Clerk EVS 2026 index; latest roll 295. "
                "Example roll https://clerk.house.gov/evs/2026/roll295.xml"
            )
        if "senate.gov" in (src.get("url") or ""):
            src["note"] = "Senate LIS 119th Congress 2nd session vote menu; latest vote 231."
    congress["sources"] = sources
    congress["prior_extract"] = {
        "retrieved_at": "2026-09-02T18:26:00Z",
        "row_count": 218,
        "per_incumbent": {"C001055": 59, "T000487": 59, "H001042": 50, "S001194": 50},
    }
    return congress


def merge_meta() -> None:
    meta_path = OUT / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    for src in meta.get("sources") or []:
        if "clerk.house.gov/evs/2026/index" in (src.get("url") or ""):
            src["retrieved_at"] = RETRIEVED
            src["note"] = "House Clerk EVS 2026 roll-call index. Case and Tokuda through official roll 295."
        if src.get("url") == "https://clerk.house.gov/evs/2026/roll283.xml":
            src["note"] = "Example House Clerk EVS roll-call XML (roll 283; extract now through 295)."
    extracts = meta.setdefault("vote_extracts", {})
    extracts["congress"] = {
        "path": "/data/congress-votes.json",
        "retrieved_at": RETRIEVED,
        "row_count": 224,
        "by_incumbent": {
            "C001055": 62,
            "T000487": 62,
            "H001042": 50,
            "S001194": 50,
        },
        "disagreement_flags": [],
    }
    if (extracts.get("hawaii") or {}).get("counts", {}).get("frozen_named_votes") != 1241:
        raise SystemExit("refusing to change HI capitol 1241 freeze metadata")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    assert_frozen()
    hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
    sd = hi["nominees"].get("State Senator, Dist 18 Vacancy") or []
    kit = next((n for n in sd if (n.get("name") or "") == "KITASHIMA, Kelly Puamailani"), None)
    if not kit:
        raise SystemExit("Kitashima missing; refusing to ship votes that would imply a wipe")
    if (kit.get("donors") or {}).get("status") != "empty":
        raise SystemExit("Kitashima CSC empty status missing; refusing")
    csc = json.loads((OUT / "csc-donors.json").read_text(encoding="utf-8"))
    if csc.get("row_count") != 18875:
        raise SystemExit(f"CSC {csc.get('row_count')} != 18875; refusing")
    if "KITASHIMA, Kelly Puamailani" not in (csc.get("by_candidate") or {}):
        raise SystemExit("Kitashima CSC empty row missing; refusing")
    hivotes = json.loads((OUT / "hawaii-votes.json").read_text(encoding="utf-8"))
    frozen = (hivotes.get("counts") or {}).get("frozen_named_votes")
    if frozen != 1241:
        raise SystemExit(f"HI capitol freeze {frozen} != 1241; refusing")
    fec = json.loads((OUT / "donors.json").read_text(encoding="utf-8"))
    if fec.get("retrieved_at") != "2026-08-31T14:40:58Z":
        raise SystemExit("FEC retrieved_at changed; refusing")
    if "KITASHIMA" in json.dumps(fec.get("by_candidate") or {}).upper():
        raise SystemExit("refusing to invent Kitashima as a federal FEC donor")

    packaged = None
    for d in PACKAGE_DIRS:
        p = d / "congress-votes.json"
        if p.is_file():
            packaged = json.loads(p.read_text(encoding="utf-8"))
            print(f"using packaged {p}", flush=True)
            break
    if packaged and packaged.get("row_count") == 224:
        congress = packaged
        if congress.get("retrieved_at") != RETRIEVED:
            congress["retrieved_at"] = RETRIEVED
        byc = congress.get("by_incumbent") or {}
        if (byc.get("C001055") or {}).get("item_count_all") != 62:
            raise SystemExit("packaged Case count != 62")
        if ((byc.get("H001042") or {}).get("items") or [{}])[0].get("roll_call_number") != 231:
            raise SystemExit("packaged Senate latest != 231")
    else:
        if packaged:
            print("packaged congress-votes present but not 224; rebuilding from Clerk XML", flush=True)
        congress = json.loads((OUT / "congress-votes.json").read_text(encoding="utf-8"))
        congress = apply_delta(congress)

    (OUT / "congress-votes.json").write_text(
        json.dumps(congress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    merge_meta()
    assert_frozen()
    print(
        json.dumps(
            {
                "congress_rows": 224,
                "added_house_facts": 6,
                "rolls": ROLLS,
                "case": 62,
                "tokuda": 62,
                "senate_231_unchanged": True,
                "hawaii_capitol_1241_unchanged": True,
                "csc_kitashima_empty_unchanged": True,
                "fec_unchanged": True,
                "kitashima_in_fec_donors_json": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
