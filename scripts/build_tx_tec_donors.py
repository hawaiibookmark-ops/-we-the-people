#!/usr/bin/env python3
"""Official Texas Ethics Commission itemized contributions 2025–2026 from TEC_CF_CSV.zip."""

from __future__ import annotations

import csv
import heapq
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T14:48:00Z"
ZIP_URL = "https://www.ethics.state.tx.us/data/search/cf/TEC_CF_CSV.zip"
LANDING = "https://www.ethics.state.tx.us/search/cf/"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "tx"
STUB = ROOT / "public" / "data" / "tx.json"
CACHE = Path("/tmp/tx-tec/TEC_CF_CSV.zip")
CAP = 25


def contrib_name(row: dict) -> str:
    org = (row.get("contributorNameOrganization") or "").strip()
    first = (row.get("contributorNameFirst") or "").strip()
    last = (row.get("contributorNameLast") or "").strip()
    return org or " ".join(p for p in (first, last) if p)


def slim(row: dict) -> dict:
    name = contrib_name(row)
    if not name:
        raise SystemExit("TEC row missing official contributor name")
    try:
        amount = float(row.get("contributionAmount") or 0)
    except ValueError:
        amount = 0.0
    raw = (row.get("contributionDt") or "").strip()
    date = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 and raw.isdigit() else raw or None
    return {
        "contributor_name": name,
        "amount": amount,
        "date": date,
        "city": (row.get("contributorStreetCity") or "").strip() or None,
        "state": (row.get("contributorStreetStateCd") or "").strip() or None,
        "employer": (row.get("contributorEmployer") or "").strip() or None,
        "retrieved_at": RETRIEVED,
        "source_url": ZIP_URL,
    }


def in_window(row: dict) -> bool:
    raw = (row.get("contributionDt") or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        year = int(raw[:4])
        return year in {2025, 2026}
    return False


def main() -> int:
    if not CACHE.exists() or CACHE.stat().st_size < 1_000_000:
        raise SystemExit(f"missing official TEC zip {CACHE}")
    heaps: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    seq = 0
    total = 0
    with zipfile.ZipFile(CACHE) as zf:
        names = sorted(n for n in zf.namelist() if n.lower().startswith("contribs_") and n.lower().endswith(".csv"))
        print(f"TEC contrib files {len(names)}", flush=True)
        for name in names:
            with zf.open(name) as fh:
                text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="")
                reader = csv.DictReader(text)
                for row in reader:
                    if not in_window(row):
                        continue
                    if (row.get("itemizeFlag") or "").strip().upper() == "N":
                        continue
                    filer = (row.get("filerName") or "").strip()
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
            print(f"  {name} running total={total} filers={len(heaps)}", flush=True)
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
            "Official Texas Ethics Commission TEC_CF_CSV.zip itemized contributions "
            "(contributionDt 2025–2026). Street addresses and ZIP omitted. Names copied "
            "from the official file only. Donor lists are not sold. No Ballotpedia."
        ),
        "source_url": ZIP_URL,
        "landing_url": LANDING,
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
    dest = OUT_DIR / "tec-donors.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    fec = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    if fec.get("path") == "/data/tx/fec-donors.json" or fec.get("status") == "partial":
        stub.setdefault("state_filings", {})["federal_fec"] = fec
    stub["election"] = {
        "jurisdiction": "Texas",
        "state_code": "TX",
        "general_date": "2026-11-03",
        "note": (
            "Official Texas SOS 2026 general ballot certification PDF, TEC itemized 2025–2026 "
            "contributions, Clerk/LIS federal votes, and federal FEC Schedule A $200+. "
            "Donor lists are not sold."
        ),
    }
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["tec_zip"] = ZIP_URL
    filings["tec_landing"] = LANDING
    filings["donors"] = {
        "status": "sourced",
        "path": "/data/tx/tec-donors.json",
        "source_url": ZIP_URL,
        "retrieved_at": RETRIEVED,
        "counts": payload["counts"],
        "do_not_sell_donor_lists": True,
    }
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    for url, note in ((ZIP_URL, "Texas Ethics Commission TEC_CF_CSV.zip"), (LANDING, "TEC campaign-finance search / bulk")):
        if url not in have:
            sources.append({"url": url, "retrieved_at": RETRIEVED, "note": note})
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest} rows={total} filers={len(by_candidate)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
