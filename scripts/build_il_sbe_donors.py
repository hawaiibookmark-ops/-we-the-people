#!/usr/bin/env python3
"""Build Illinois SBE Schedule A extract from official Receipts.txt."""

from __future__ import annotations

import csv
import heapq
import json
import sys
import time
import urllib.error
import urllib.request

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(8_000_000)
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RECEIPTS_URL = "https://downloads.elections.il.gov/Receipts.txt"
COMMITTEES_URL = "https://downloads.elections.il.gov/Committees.txt"
LANDING = "https://elections.il.gov/CampaignDisclosure/DownloadCDDataFiles.aspx"
CACHE = Path("/tmp/il-sbe")
RETRIEVED_AT = "2026-09-02T13:26:08Z"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "il"
STUB = ROOT / "public" / "data" / "il.json"
CAP = 25
EXPECT_ROWS = 191_759
EXPECT_COMMITTEES = 2_851
STREET_KEYS = {
    "street",
    "address",
    "addr",
    "address1",
    "address2",
    "contributor_address",
    "zip",
    "zipcode",
    "contributor_zip",
}

POLICY = (
    "Official Illinois State Board of Elections Receipts.txt only "
    "(RcvDate 2025–2026, Archived is not true). "
    "Street addresses omitted. Names copied from the official file only and never invented. "
    "Donor lists are not sold. No Ballotpedia. No scores."
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path, retries: int = 5) -> Path:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/plain,*/*"})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                dest.write_bytes(resp.read())
            return dest
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            wait = 4 * (2**attempt)
            print(f"retry {url} attempt={attempt + 1} wait={wait}s err={exc}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Failed IL SBE download {url}: {last_err}")


def official_text(row: dict, *keys: str) -> str | None:
    for key in keys:
        val = row.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text:
            return text
    return None


def official_amount(row: dict) -> float | None:
    raw = row.get("Amount")
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def contributor_name(row: dict) -> str | None:
    first = official_text(row, "FirstName")
    last = official_text(row, "LastOnlyName")
    if first and last:
        return f"{first} {last}"
    return last or first


def is_archived(row: dict) -> bool:
    return (official_text(row, "Archived") or "").casefold() != "false"


def valid_d2(row: dict) -> bool:
    return (official_text(row, "D2Part") or "") in {"1A", "2A", "3A", "4A", "5A"}


def in_cycle(row: dict) -> bool:
    dt = official_text(row, "RcvDate") or ""
    return dt.startswith("2025") or dt.startswith("2026")


def slim_item(row: dict) -> dict:
    item = {
        "contributor_name": contributor_name(row),
        "amount": official_amount(row),
        "date": (official_text(row, "RcvDate") or "")[:10] or None,
        "city": official_text(row, "City"),
        "state": official_text(row, "State"),
        "employer": official_text(row, "Employer"),
        "occupation": official_text(row, "Occupation"),
        "d2_part": official_text(row, "D2Part"),
    }
    if STREET_KEYS & {k.lower() for k in item}:
        raise RuntimeError("street field leaked into slim item")
    return item


def load_committees(path: Path) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            cid = official_text(row, "ID")
            if not cid:
                continue
            by_id[cid] = {
                "committee_id": cid,
                "committee_name": official_text(row, "Name"),
                "refer_name": official_text(row, "ReferName"),
                "committee_type": official_text(row, "TypeOfCommittee"),
                "status": official_text(row, "Status"),
            }
    return by_id


def pick_meta(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def build() -> None:
    retrieved = RETRIEVED_AT or now_iso()
    receipts_path = fetch(RECEIPTS_URL, CACHE / "Receipts.txt")
    committees_path = fetch(COMMITTEES_URL, CACHE / "Committees.txt")
    print(f"receipts={receipts_path} bytes={receipts_path.stat().st_size}", flush=True)
    print(f"committees={committees_path} bytes={committees_path.stat().st_size}", flush=True)
    committees = load_committees(committees_path)
    print(f"committee index={len(committees)}", flush=True)

    heaps: dict[str, list[tuple]] = defaultdict(list)
    item_counts: dict[str, int] = defaultdict(int)
    type_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    row_count = 0
    scanned = 0

    with receipts_path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            scanned += 1
            if not in_cycle(row) or is_archived(row) or not valid_d2(row):
                continue
            cid = official_text(row, "CommitteeID")
            if not cid:
                continue
            row_count += 1
            item_counts[cid] += 1
            d2 = official_text(row, "D2Part")
            if d2:
                type_counts[cid][d2] += 1
            amt = official_amount(row)
            heap_key = (
                amt if amt is not None else float("-inf"),
                official_text(row, "RcvDate") or "",
                official_text(row, "ID") or "",
            )
            item = slim_item(row)
            heap = heaps[cid]
            entry = (heap_key, item)
            if len(heap) < CAP:
                heapq.heappush(heap, entry)
            elif heap_key > heap[0][0]:
                heapq.heapreplace(heap, entry)
            if scanned % 500_000 == 0:
                print(f"scanned={scanned} kept={row_count} committees={len(item_counts)}", flush=True)

    print(f"scanned={scanned} kept={row_count} committees={len(item_counts)}", flush=True)
    if row_count != EXPECT_ROWS or len(item_counts) != EXPECT_COMMITTEES:
        raise SystemExit(
            f"expected {EXPECT_ROWS}/{EXPECT_COMMITTEES}, got {row_count}/{len(item_counts)}"
        )

    by_candidate: dict[str, dict] = {}
    for cid in sorted(item_counts, key=lambda c: (
        (committees.get(c) or {}).get("committee_name") or "",
        c,
    )):
        meta = committees.get(cid) or {}
        name = meta.get("committee_name") or cid
        key = name
        n = 2
        while key in by_candidate:
            key = f"{name} ({cid})" if n == 2 else f"{name} ({cid}/{n})"
            n += 1
        ranked_items = [
            item
            for _k, item in sorted(
                heaps[cid],
                key=lambda kv: (
                    kv[0][0] == float("-inf"),
                    -kv[0][0] if kv[0][0] != float("-inf") else 0.0,
                    kv[0][1],
                    kv[0][2],
                ),
            )
        ]
        by_candidate[key] = {
            "committee_name": name,
            "committee_id": cid,
            "refer_name": meta.get("refer_name"),
            "committee_type": meta.get("committee_type"),
            "committee_status": meta.get("status"),
            "d2_part": pick_meta(type_counts[cid]),
            "matched_to_site": False,
            "status": "unmatched_no_roster",
            "item_count_all": item_counts[cid],
            "items": ranked_items,
        }

    payload = {
        "policy": POLICY,
        "by_candidate": by_candidate,
        "retrieved_at": retrieved,
        "source_url": RECEIPTS_URL,
        "landing_url": LANDING,
        "attribution": "Illinois State Board of Elections campaign-disclosure receipts",
        "row_count": row_count,
        "filer_count": len(by_candidate),
        "counts": {
            "rows": row_count,
            "filers": len(by_candidate),
            "items_per_filer_cap": CAP,
            "election_year": 2026,
            "rcv_years": "2025-2026",
            "archived_excluded": True,
        },
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
        "scope": (
            "Illinois SBE Receipts.txt Schedule A-style receipts with RcvDate 2025–2026. "
            "Archived (superseded) rows omitted. Top 25 gifts per committee by amount."
        ),
    }

    stub: dict = {}
    if STUB.exists():
        stub = json.loads(STUB.read_text(encoding="utf-8"))
    election = stub.setdefault("election", {})
    election["jurisdiction"] = "Illinois"
    election["state_code"] = "IL"
    election["general_date"] = election.get("general_date")
    election["note"] = (
        "Official Illinois SBE Schedule A receipts (RcvDate 2025–2026, not archived) first. "
        "Federal FEC Schedule A $200+ alongside when present. Ballots and votes TBD. "
        "Donor lists are not sold."
    )
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["sbe"] = RECEIPTS_URL
    filings["sbe_landing"] = LANDING
    filings["donors"] = {
        "status": "sourced",
        "path": "/data/il/sbe-donors.json",
        "source_url": RECEIPTS_URL,
        "retrieved_at": retrieved,
        "counts": {
            "rows": row_count,
            "filers": len(by_candidate),
            "items_per_filer_cap": CAP,
            "election_year": 2026,
        },
        "do_not_sell_donor_lists": True,
    }
    existing_fec = filings.get("federal_fec") if isinstance(filings.get("federal_fec"), dict) else {}
    fec_path = OUT_DIR / "fec-donors.json"
    fec_counts = existing_fec.get("counts")
    if fec_path.exists():
        fec_payload = json.loads(fec_path.read_text(encoding="utf-8"))
        fec_counts = fec_payload.get("counts") or fec_counts
    federal_fec = {
        "status": "partial",
        "path": "/data/il/fec-donors.json",
        "scope": "Federal FEC Schedule A $200+ only (indiv26 + cn26 CAND_PCC).",
        "source_url": existing_fec.get("source_url")
        or "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip",
        "retrieved_at": existing_fec.get("retrieved_at") or retrieved,
        "do_not_sell_donor_lists": True,
    }
    if fec_counts:
        federal_fec["counts"] = fec_counts
    filings["federal_fec"] = federal_fec
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    for src in (
        {"url": RECEIPTS_URL, "retrieved_at": retrieved, "note": "Illinois SBE Receipts.txt"},
        {"url": COMMITTEES_URL, "retrieved_at": retrieved, "note": "Illinois SBE Committees.txt"},
        {"url": LANDING, "retrieved_at": retrieved, "note": "Illinois SBE campaign-disclosure downloads"},
    ):
        if src["url"] not in have:
            sources.append(src)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sbe-donors.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT_DIR / 'sbe-donors.json'} rows={row_count} filers={len(by_candidate)} retrieved={retrieved}",
        flush=True,
    )


if __name__ == "__main__":
    build()
