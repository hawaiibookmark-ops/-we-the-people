#!/usr/bin/env python3
"""Build Washington PDC Schedule A extract from official data.wa.gov SODA."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
SODA = "https://data.wa.gov/resource/kv7h-kjye.json"
DATASET = "https://data.wa.gov/Politics/Contributions-to-Candidates-and-Political-Committe/kv7h-kjye"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "wa"
STUB = ROOT / "public" / "data" / "wa.json"
PAGE = 50_000
STREET_KEYS = {
    "street",
    "address",
    "addr",
    "contributor_address",
    "contributor_street_1",
    "contributor_street_2",
    "contributor_zip",
    "contributor_location",
    "zip",
    "zipcode",
}

POLICY = (
    "Official Washington PDC data.wa.gov SODA kv7h-kjye only (election_year=2026). "
    "Street addresses omitted. Names copied from the official file only and never invented. "
    "Donor lists are not sold (RCW 42.56.070(9)). No Ballotpedia. No scores."
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_page(offset: int, retries: int = 5) -> list[dict]:
    params = {
        "$where": "election_year='2026'",
        "$order": "id",
        "$limit": str(PAGE),
        "$offset": str(offset),
    }
    url = f"{SODA}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, list):
                raise RuntimeError(f"Unexpected SODA payload type: {type(payload)}")
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_err = exc
            wait = 4 * (2**attempt)
            print(f"retry offset={offset} attempt={attempt + 1} wait={wait}s err={exc}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Failed SODA page offset={offset}: {last_err}")


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
        return float(raw)
    except (TypeError, ValueError):
        return None


def official_date(row: dict) -> str | None:
    raw = official_text(row, "receipt_date")
    if not raw:
        return None
    return raw[:10]


def pick_meta(rows: list[dict], key: str) -> str | None:
    counts: dict[str, int] = {}
    for row in rows:
        val = official_text(row, key)
        if not val:
            continue
        counts[val] = counts.get(val, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def slim_item(row: dict) -> dict:
    item = {
        "contributor_name": official_text(row, "contributor_name"),
        "contributor_type": official_text(row, "contributor_category", "code"),
        "amount": official_amount(row),
        "date": official_date(row),
        "city": official_text(row, "contributor_city"),
        "state": official_text(row, "contributor_state"),
        "cash_or_in_kind": official_text(row, "cash_or_in_kind"),
        "code": official_text(row, "code"),
    }
    if STREET_KEYS & {k.lower() for k in item}:
        raise RuntimeError("street field leaked into slim item")
    return item


def build() -> None:
    retrieved = now_iso()
    rows: list[dict] = []
    offset = 0
    while True:
        page = fetch_page(offset)
        print(f"fetched offset={offset} n={len(page)}", flush=True)
        rows.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
        time.sleep(0.4)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        name = official_text(row, "filer_name")
        if not name:
            name = official_text(row, "filer_id")
        if not name:
            continue
        grouped[name].append(row)

    by_candidate: dict[str, dict] = {}
    for filer_name in sorted(grouped):
        filer_rows = grouped[filer_name]
        ranked = sorted(
            filer_rows,
            key=lambda r: (
                official_amount(r) is None,
                -(official_amount(r) or 0.0),
                official_date(r) or "",
                official_text(r, "id") or "",
            ),
        )
        by_candidate[filer_name] = {
            "candidate_name": filer_name,
            "pdc_filer_name": filer_name,
            "type": pick_meta(filer_rows, "type"),
            "office": pick_meta(filer_rows, "office"),
            "position": pick_meta(filer_rows, "position"),
            "jurisdiction": pick_meta(filer_rows, "jurisdiction"),
            "filer_id": pick_meta(filer_rows, "filer_id"),
            "matched_to_site": False,
            "status": "unmatched_no_roster",
            "item_count_all": len(filer_rows),
            "items": [slim_item(r) for r in ranked[:25]],
        }

    payload = {
        "policy": POLICY,
        "by_candidate": by_candidate,
        "retrieved_at": retrieved,
        "source_url": SODA,
        "dataset_page": DATASET,
        "attribution": "Washington State Public Disclosure Commission (PDC)",
        "row_count": len(rows),
        "filer_count": len(by_candidate),
        "counts": {
            "rows": len(rows),
            "filers": len(by_candidate),
            "items_per_filer_cap": 25,
            "election_year": 2026,
        },
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
        "scope": "Washington 2026 PDC contributions. Top 25 contributions per filer by amount.",
    }
    stub = {
        "election": {
            "jurisdiction": "Washington",
            "state_code": "WA",
            "general_date": None,
            "note": "State module first populate: official PDC Schedule A donors only. Candidate/ballot and vote packages TBD.",
        },
        "state_filings": {
            "wired": True,
            "pdc_public": "https://www.pdc.wa.gov/",
            "pdc_data": DATASET,
            "donors": {
                "status": "sourced",
                "path": "/data/wa/pdc-donors.json",
                "source_url": SODA,
                "retrieved_at": retrieved,
                "counts": {
                    "rows": len(rows),
                    "filers": len(by_candidate),
                    "items_per_filer_cap": 25,
                    "election_year": 2026,
                },
                "do_not_sell_donor_lists": True,
            },
        },
        "nominees": {},
        "geo_by_zip": {},
        "sources": [{"url": SODA, "retrieved_at": retrieved}],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "pdc-donors.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT_DIR / 'pdc-donors.json'} rows={len(rows)} filers={len(by_candidate)} retrieved={retrieved}",
        flush=True,
    )


if __name__ == "__main__":
    build()
