#!/usr/bin/env python3
"""Build Michigan MiTN Schedule A extract from official CFR export ZIP id 21077."""

from __future__ import annotations

import csv
import heapq
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
ZIP_ID = "21077"
ZIP_URL = (
    "https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do"
    "?page=gov.mi.boe.component.cfrexport.page.cfrexportfile&id=21077"
)
LANDING = (
    "https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do"
    "?page=gov.mi.boe.component.cfrexport.page.cfrexportdownload"
)
SOS_CFR = "https://www.michigan.gov/sos/elections/disclosure/cfr"
CACHE = Path("/tmp/mi-mitn/21077.bin")
RETRIEVED_AT = "2026-09-02T13:00:04Z"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "mi"
STUB = ROOT / "public" / "data" / "mi.json"
CAP = 25
STREET_KEYS = {
    "street",
    "address",
    "addr",
    "address1",
    "address2",
    "contributor_address",
    "contributor_street_1",
    "contributor_street_2",
    "zip",
    "zipcode",
    "contributor_zip",
}

POLICY = (
    "Official Michigan Bureau of Elections MiTN CFR contributions export (ZIP id 21077) only. "
    "Street addresses omitted. Names copied from the official file only and never invented. "
    "Donor lists are not sold. No Ballotpedia. No scores."
)

HEADER = [
    "doc_seq_no",
    "contribution_id",
    "cont_detail_id",
    "doc_stmnt_year",
    "doc_type_desc",
    "com_legal_name",
    "common_name_acronym",
    "cfr_com_id",
    "com_type",
    "can_first_name",
    "can_last_name",
    "contribtype",
    "contributor_f_name",
    "contributor_l_name_or_org",
    "contributor_address",
    "contributor_city",
    "contributor_state",
    "contributor_zip",
    "contributor_occupation",
    "contributor_employer",
    "received_date",
    "amount",
    "aggregate",
    "extra_desc",
    "fundraiser",
    "can_political_party",
    "can_office_sought",
    "can_district_sought",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_zip(retries: int = 5) -> bytes:
    if CACHE.exists() and CACHE.stat().st_size > 1_000_000:
        print(f"using cached ZIP {CACHE} bytes={CACHE.stat().st_size}", flush=True)
        return CACHE.read_bytes()
    req = urllib.request.Request(
        ZIP_URL,
        headers={"User-Agent": UA, "Accept": "application/zip,*/*"},
    )
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                blob = resp.read()
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_bytes(blob)
            return blob
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            wait = 4 * (2**attempt)
            print(f"retry zip attempt={attempt + 1} wait={wait}s err={exc}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Failed MiTN ZIP download: {last_err}")


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
    raw = row.get("amount")
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def contributor_name(row: dict) -> str | None:
    first = official_text(row, "contributor_f_name")
    last = official_text(row, "contributor_l_name_or_org")
    if first and last:
        return f"{first} {last}"
    return last or first


def pick_meta(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def slim_item(row: dict) -> dict:
    item = {
        "contributor_name": contributor_name(row),
        "contributor_type": official_text(row, "contribtype"),
        "amount": official_amount(row),
        "date": official_text(row, "received_date"),
        "city": official_text(row, "contributor_city"),
        "state": official_text(row, "contributor_state"),
        "employer": official_text(row, "contributor_employer"),
        "occupation": official_text(row, "contributor_occupation"),
    }
    if STREET_KEYS & {k.lower() for k in item}:
        raise RuntimeError("street field leaked into slim item")
    return item


def iter_contribution_rows(blob: bytes):
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = sorted(
            n for n in zf.namelist() if n.lower().startswith("2026_mi_cfr_contributions") and n.lower().endswith(".txt")
        )
        if not names:
            raise RuntimeError(f"No 2026_mi_cfr_contributions*.txt in MiTN ZIP: {zf.namelist()}")
        for name in names:
            with zf.open(name) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
                reader = csv.DictReader(text, delimiter="\t")
                if reader.fieldnames and [h.strip() for h in reader.fieldnames] != HEADER:
                    raise RuntimeError(f"Unexpected header in {name}: {reader.fieldnames}")
                for row in reader:
                    yield row


def build() -> None:
    retrieved = RETRIEVED_AT or now_iso()
    print("fetching", ZIP_URL, flush=True)
    blob = fetch_zip()

    heaps: dict[str, list[tuple]] = defaultdict(list)
    item_counts: dict[str, int] = defaultdict(int)
    meta_counts: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    row_count = 0
    empty_filer = 0

    meta_fields = (
        "common_name_acronym",
        "cfr_com_id",
        "com_type",
        "can_first_name",
        "can_last_name",
        "can_office_sought",
        "can_district_sought",
    )

    for row in iter_contribution_rows(blob):
        row_count += 1
        filer = official_text(row, "com_legal_name")
        if not filer:
            empty_filer += 1
            continue
        item_counts[filer] += 1
        for field in meta_fields:
            val = official_text(row, field)
            if val:
                meta_counts[filer][field][val] += 1
        amt = official_amount(row)
        heap_key = (
            amt if amt is not None else float("-inf"),
            official_text(row, "received_date") or "",
            official_text(row, "contribution_id") or "",
            official_text(row, "cont_detail_id") or "",
        )
        item = slim_item(row)
        heap = heaps[filer]
        entry = (heap_key, item)
        if len(heap) < CAP:
            heapq.heappush(heap, entry)
        elif heap_key > heap[0][0]:
            heapq.heapreplace(heap, entry)
        if row_count % 200_000 == 0:
            print(f"streamed rows={row_count} filers={len(item_counts)}", flush=True)

    print(
        f"parsed rows={row_count} filers={len(item_counts)} empty_filer={empty_filer}",
        flush=True,
    )

    by_candidate: dict[str, dict] = {}
    for filer in sorted(item_counts):
        ranked_items = [
            item
            for _key, item in sorted(
                heaps[filer],
                key=lambda kv: (
                    kv[0][0] == float("-inf"),
                    -kv[0][0] if kv[0][0] != float("-inf") else 0.0,
                    kv[0][1],
                    kv[0][2],
                    kv[0][3],
                ),
            )
        ]
        meta = meta_counts[filer]
        by_candidate[filer] = {
            "committee_name": filer,
            "common_name_acronym": pick_meta(meta["common_name_acronym"]),
            "cfr_com_id": pick_meta(meta["cfr_com_id"]),
            "committee_type": pick_meta(meta["com_type"]),
            "candidate_first_name": pick_meta(meta["can_first_name"]),
            "candidate_last_name": pick_meta(meta["can_last_name"]),
            "office_sought": pick_meta(meta["can_office_sought"]),
            "district_sought": pick_meta(meta["can_district_sought"]),
            "matched_to_site": False,
            "status": "unmatched_no_roster",
            "item_count_all": item_counts[filer],
            "items": ranked_items,
        }

    payload = {
        "policy": POLICY,
        "by_candidate": by_candidate,
        "retrieved_at": retrieved,
        "source_url": ZIP_URL,
        "landing_url": LANDING,
        "attribution": "Michigan Bureau of Elections MiTN campaign-finance disclosure",
        "row_count": row_count,
        "filer_count": len(by_candidate),
        "counts": {
            "rows": row_count,
            "filers": len(by_candidate),
            "items_per_filer_cap": CAP,
            "election_year": 2026,
        },
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
        "scope": "Michigan 2026 MiTN Schedule A contributions (ZIP id 21077). Top 25 gifts per filer by amount.",
    }
    stub = {
        "election": {
            "jurisdiction": "Michigan",
            "state_code": "MI",
            "general_date": None,
            "note": "State module first populate: official MiTN Schedule A donors only. Candidate/ballot and vote packages TBD.",
        },
        "state_filings": {
            "wired": True,
            "mitn": ZIP_URL,
            "mitn_landing": LANDING,
            "sos_cfr": SOS_CFR,
            "donors": {
                "status": "sourced",
                "path": "/data/mi/mitn-donors.json",
                "source_url": ZIP_URL,
                "retrieved_at": retrieved,
                "counts": {
                    "rows": row_count,
                    "filers": len(by_candidate),
                    "items_per_filer_cap": CAP,
                    "election_year": 2026,
                },
                "do_not_sell_donor_lists": True,
            },
        },
        "nominees": {},
        "geo_by_zip": {},
        "sources": [
            {"url": ZIP_URL, "retrieved_at": retrieved},
            {"url": LANDING, "retrieved_at": retrieved},
            {"url": SOS_CFR, "retrieved_at": retrieved},
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "mitn-donors.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT_DIR / 'mitn-donors.json'} rows={row_count} filers={len(by_candidate)} retrieved={retrieved}",
        flush=True,
    )


if __name__ == "__main__":
    build()
