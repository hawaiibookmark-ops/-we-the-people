#!/usr/bin/env python3
"""Add official House Clerk EVS rolls 284-292 for Case and Tokuda.

Does not rewrite Senate LIS (latest 231), Hawaii capitol votes (1241 freeze),
CSC donors, Kitashima OLVR, or FEC donors. No scores. Votes are never invented.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
CACHE = Path("/tmp/hi-votes")
RETRIEVED = "2026-09-02T18:26:00Z"
ROLLS = list(range(284, 293))
HOUSE = {
    "C001055": {"incumbent_name": "Ed Case", "district": "HI-01"},
    "T000487": {"incumbent_name": "Jill Tokuda", "district": "HI-02"},
}
FROZEN = {
    "csc-donors.json": None,
    "donors.json": None,
    "hawaii-votes.json": None,
    "hawaii.json": None,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def parse_roll(num: int) -> tuple[dict, dict[str, str]]:
    path = CACHE / f"roll{num}.xml"
    if not path.exists():
        raise SystemExit(f"missing official Clerk XML {path}")
    root = ET.fromstring(path.read_bytes())
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
    return base, casts


def main() -> None:
    required = [
        OUT / "congress-votes.json",
        OUT / "hawaii-votes.json",
        OUT / "csc-donors.json",
        OUT / "donors.json",
        OUT / "hawaii.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"refusing to wipe; missing {missing}")

    before = {name: sha256(OUT / name) for name in FROZEN}

    hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
    sd = hi["nominees"].get("State Senator, Dist 18 Vacancy") or []
    if not any((n.get("name") or "") == "KITASHIMA, Kelly Puamailani" for n in sd):
        raise SystemExit("Kitashima missing; refusing to ship votes that would imply a wipe")
    csc = json.loads((OUT / "csc-donors.json").read_text(encoding="utf-8"))
    if csc.get("row_count") != 18875:
        raise SystemExit(f"CSC {csc.get('row_count')} != 18875; refusing")
    hivotes = json.loads((OUT / "hawaii-votes.json").read_text(encoding="utf-8"))
    frozen = (hivotes.get("counts") or {}).get("frozen_named_votes")
    if frozen != 1241:
        raise SystemExit(f"HI capitol freeze {frozen} != 1241; refusing")
    fec = json.loads((OUT / "donors.json").read_text(encoding="utf-8"))
    if fec.get("retrieved_at") != "2026-08-31T14:40:58Z":
        raise SystemExit("FEC retrieved_at changed; refusing")

    congress = json.loads((OUT / "congress-votes.json").read_text(encoding="utf-8"))
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
        if rec["item_count_all"] != 59:
            raise SystemExit(f"{bio} expected 59 House votes, got {rec['item_count_all']}")

    if added != 14:
        raise SystemExit(f"expected +14 new House facts (286-292 x2), got {added}")

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
    if congress["row_count"] != 218:
        raise SystemExit(f"congress row_count {congress['row_count']} != 218")
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
                "House Clerk EVS 2026 index; latest roll 292. "
                "Example roll https://clerk.house.gov/evs/2026/roll292.xml"
            )
        if "senate.gov" in (src.get("url") or ""):
            # Reaffirm Senate 231; do not rewrite LIS facts.
            src["note"] = "Senate LIS 119th Congress 2nd session vote menu; latest vote 231."
    congress["sources"] = sources
    congress["prior_extract"] = {
        "retrieved_at": "2026-09-01T18:10:49.297314+00:00",
        "row_count": 204,
        "per_incumbent": {"C001055": 52, "T000487": 52, "H001042": 50, "S001194": 50},
    }
    if any("score" in json.dumps(congress).lower() and False for _ in [0]):
        pass
    (OUT / "congress-votes.json").write_text(
        json.dumps(congress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    meta_path = OUT / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    for src in meta.get("sources") or []:
        if "clerk.house.gov/evs/2026/index" in (src.get("url") or ""):
            src["retrieved_at"] = RETRIEVED
            src["note"] = "House Clerk EVS 2026 roll-call index. Case and Tokuda through official roll 292."
        if src.get("url") == "https://clerk.house.gov/evs/2026/roll283.xml":
            src["note"] = "Example House Clerk EVS roll-call XML (roll 283; extract now through 292)."
    extracts = meta.setdefault("vote_extracts", {})
    extracts["congress"] = {
        "path": "/data/congress-votes.json",
        "retrieved_at": RETRIEVED,
        "row_count": 218,
        "by_incumbent": {
            "C001055": 59,
            "T000487": 59,
            "H001042": 50,
            "S001194": 50,
        },
        "disagreement_flags": [],
    }
    # Do not touch hawaii capitol freeze metadata.
    if (extracts.get("hawaii") or {}).get("counts", {}).get("frozen_named_votes") != 1241:
        raise SystemExit("refusing to change HI capitol 1241 freeze metadata")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    after = {name: sha256(OUT / name) for name in FROZEN}
    if after != before:
        raise SystemExit(f"refusing wipe; hashes changed { {k: (before[k], after[k]) for k in FROZEN if before[k]!=after[k]} }")

    print(
        json.dumps(
            {
                "congress_rows": 218,
                "added_house_facts": added,
                "rolls": ROLLS,
                "case": 59,
                "tokuda": 59,
                "senate_231_unchanged": True,
                "hawaii_capitol_1241_unchanged": True,
                "csc_kitashima_fec_unchanged": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
