#!/usr/bin/env python3
"""Official NYSBOE Schedule A–D via Open NY SODA e9ss-239a (election_year=2026)."""

from __future__ import annotations

import heapq
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T14:45:00Z"
SODA = "https://data.ny.gov/resource/e9ss-239a.json"
LANDING = "https://data.ny.gov/Government-Finance/Campaign-Finance-Disclosure-Reports-Data-Beginning/e9ss-239a"
NYSBOE = "https://publicreporting.elections.ny.gov/"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "ny"
STUB = ROOT / "public" / "data" / "ny.json"
CAP = 25
EXPECT_ROWS = 700704
WHERE = "election_year='2026' AND filing_sched_abbrev in('A','B','C','D')"


SELECT = (
    "cand_comm_name,org_amt,sched_date,flng_ent_name,flng_ent_first_name,flng_ent_last_name,"
    "flng_ent_city,flng_ent_state,cntrbr_type_desc,filing_sched_abbrev"
)


def soda_page(offset: int, limit: int = 50000) -> list[dict]:
    params = {
        "$select": SELECT,
        "$where": WHERE,
        "$limit": str(limit),
        "$offset": str(offset),
        "$order": "sched_date",
    }
    url = SODA + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def contrib_name(row: dict) -> str:
    org = (row.get("flng_ent_name") or "").strip()
    first = (row.get("flng_ent_first_name") or "").strip()
    last = (row.get("flng_ent_last_name") or "").strip()
    return org or " ".join(p for p in (first, last) if p)


def slim(row: dict) -> dict:
    name = contrib_name(row)
    if not name:
        raise SystemExit("NYSBOE row missing official contributor name")
    amt = row.get("org_amt")
    try:
        amount = float(amt)
    except (TypeError, ValueError):
        amount = 0.0
    date = (row.get("sched_date") or "")[:10] or None
    return {
        "contributor_name": name,
        "amount": amount,
        "date": date,
        "city": (row.get("flng_ent_city") or "").strip() or None,
        "state": (row.get("flng_ent_state") or "").strip() or None,
        "contributor_type": (row.get("cntrbr_type_desc") or "").strip() or None,
        "schedule": (row.get("filing_sched_abbrev") or "").strip() or None,
        "retrieved_at": RETRIEVED,
        "source_url": SODA,
    }


def main() -> int:
    heaps: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    seq = 0
    offset = 0
    total = 0
    while True:
        page = soda_page(offset)
        if not page:
            break
        for row in page:
            filer = (row.get("cand_comm_name") or "").strip()
            if not filer or not contrib_name(row):
                continue
            item = slim(row)
            counts[filer] += 1
            total += 1
            rec = (item["amount"], item.get("date") or "", seq, item)
            seq += 1
            if len(heaps[filer]) < CAP:
                heapq.heappush(heaps[filer], rec)
            elif rec[0] > heaps[filer][0][0]:
                heapq.heapreplace(heaps[filer], rec)
        offset += len(page)
        print(f"  soda offset={offset} filers={len(heaps)}", flush=True)
        if len(page) < 50000:
            break
    if total < 680000:
        raise SystemExit(f"NYSBOE 2026 A-D named rows too low: {total}")
    by_candidate = {}
    for filer, heap in sorted(heaps.items()):
        items = [h[3] for h in sorted(heap, key=lambda r: (-r[0], r[1], r[2]))]
        by_candidate[filer] = {
            "committee_name": filer,
            "status": "unmatched_no_roster",
            "matched_to_site": False,
            "item_count_all": counts[filer],
            "items": items,
        }
    payload = {
        "policy": (
            "Official New York State Board of Elections campaign-finance disclosure via "
            "Open NY SODA e9ss-239a, election_year=2026, filing schedules A–D only. "
            "Street addresses and ZIP omitted. Names copied from the official file only. "
            "Donor lists are not sold. No Ballotpedia."
        ),
        "source_url": SODA,
        "landing_url": LANDING,
        "nysboe_public": NYSBOE,
        "retrieved_at": RETRIEVED,
        "row_count": total,
        "filer_count": len(by_candidate),
        "counts": {
            "rows": total,
            "filers": len(by_candidate),
            "items_per_filer_cap": CAP,
            "election_year": 2026,
        },
        "by_candidate": by_candidate,
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "nysboe-donors.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    fec = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    if fec.get("path") == "/data/ny/fec-donors.json" or fec.get("status") == "partial":
        stub.setdefault("state_filings", {})["federal_fec"] = fec
    stub["election"] = {
        "jurisdiction": "New York",
        "state_code": "NY",
        "general_date": "2026-11-03",
        "note": (
            "Official NYSBOE Schedule A–D donors (Open NY e9ss-239a, election_year=2026), "
            "Clerk/LIS federal votes, and federal FEC Schedule A $200+. Who Filed AJAX "
            "candidate list is still blocked; candidates_path is not claimed. Donor lists are not sold."
        ),
    }
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["nysboe_soda"] = SODA
    filings["nysboe_landing"] = LANDING
    filings["donors"] = {
        "status": "sourced",
        "path": "/data/ny/nysboe-donors.json",
        "source_url": SODA,
        "retrieved_at": RETRIEVED,
        "counts": payload["counts"],
        "do_not_sell_donor_lists": True,
    }
    stub["nominees"] = {}
    stub["geo_by_zip"] = {}
    if stub.get("candidates_path"):
        del stub["candidates_path"]
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    for url, note in (
        (SODA, "Open NY SODA e9ss-239a NYSBOE disclosure (2026 A-D)"),
        (LANDING, "Open NY Campaign Finance Disclosure Reports dataset"),
        (NYSBOE, "NYSBOE public reporting"),
    ):
        if url not in have:
            sources.append({"url": url, "retrieved_at": RETRIEVED, "note": note})
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest} rows={total} filers={len(by_candidate)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
