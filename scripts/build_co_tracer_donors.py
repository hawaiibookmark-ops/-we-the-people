#!/usr/bin/env python3
"""Build Colorado TRACER Schedule A extract from official bulk ContributionData."""

from __future__ import annotations

import csv
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
ZIP_URL = "https://tracer.sos.colorado.gov/PublicSite/Docs/BulkDataDownloads/2026_ContributionData.csv.zip"
LANDING = "https://tracer.sos.colorado.gov/PublicSite/DataDownload.aspx"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "co"
STUB = ROOT / "public" / "data" / "co.json"
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
    "Official Colorado TRACER bulk ContributionData (2026) from tracer.sos.colorado.gov only. "
    "Street addresses omitted. Names copied from the official file only and never invented. "
    "Donor lists are not sold. No Ballotpedia. No scores."
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_zip(retries: int = 5) -> bytes:
    req = urllib.request.Request(ZIP_URL, headers={"User-Agent": UA, "Accept": "application/zip,*/*"})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            wait = 4 * (2**attempt)
            print(f"retry zip attempt={attempt + 1} wait={wait}s err={exc}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Failed TRACER ZIP download: {last_err}")


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
    raw = row.get("ContributionAmount")
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def official_date(row: dict) -> str | None:
    raw = official_text(row, "ContributionDate")
    if not raw:
        return None
    return raw[:10]


def contributor_name(row: dict) -> str | None:
    last = official_text(row, "LastName")
    first = official_text(row, "FirstName")
    mi = official_text(row, "MI")
    suffix = official_text(row, "Suffix")
    if not any((last, first, mi, suffix)):
        return None
    given = " ".join(p for p in (first, mi) if p)
    if given or suffix:
        after = " ".join(p for p in (given, suffix) if p)
        if last and after:
            return f"{last}, {after}"
        return last or after
    return last


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
        "contributor_name": contributor_name(row),
        "contributor_type": official_text(row, "ContributorType"),
        "amount": official_amount(row),
        "date": official_date(row),
        "city": official_text(row, "City"),
        "state": official_text(row, "State"),
        "contribution_type": official_text(row, "ContributionType"),
        "receipt_type": official_text(row, "ReceiptType"),
        "employer": official_text(row, "Employer"),
        "occupation": official_text(row, "Occupation"),
    }
    if STREET_KEYS & {k.lower() for k in item}:
        raise RuntimeError("street field leaked into slim item")
    return item


def read_rows(blob: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = zf.namelist()
        csv_name = next((n for n in names if n.lower().endswith(".csv")), None)
        if not csv_name:
            raise RuntimeError(f"No CSV in TRACER ZIP: {names}")
        with zf.open(csv_name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
            return list(csv.DictReader(text))


def build() -> None:
    retrieved = now_iso()
    print("fetching", ZIP_URL, flush=True)
    blob = fetch_zip()
    rows = read_rows(blob)
    print(f"parsed rows={len(rows)}", flush=True)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        name = official_text(row, "CommitteeName")
        if not name:
            continue
        grouped[name].append(row)

    by_candidate: dict[str, dict] = {}
    for committee in sorted(grouped):
        committee_rows = grouped[committee]
        ranked = sorted(
            committee_rows,
            key=lambda r: (
                official_amount(r) is None,
                -(official_amount(r) or 0.0),
                official_date(r) or "",
                official_text(r, "RecordID") or "",
            ),
        )
        by_candidate[committee] = {
            "committee_name": committee,
            "tracer_candidate_name": pick_meta(committee_rows, "CandidateName"),
            "committee_type": pick_meta(committee_rows, "CommitteeType"),
            "co_id": pick_meta(committee_rows, "CO_ID"),
            "jurisdiction": pick_meta(committee_rows, "Jurisdiction"),
            "matched_to_site": False,
            "status": "unmatched_no_roster",
            "item_count_all": len(committee_rows),
            "items": [slim_item(r) for r in ranked[:25]],
        }

    payload = {
        "policy": POLICY,
        "by_candidate": by_candidate,
        "retrieved_at": retrieved,
        "source_url": ZIP_URL,
        "landing_url": LANDING,
        "attribution": "Colorado Secretary of State TRACER",
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
        "scope": "Colorado 2026 TRACER contributions. Top 25 contributions per committee by amount.",
    }
    stub = {
        "election": {
            "jurisdiction": "Colorado",
            "state_code": "CO",
            "general_date": None,
            "note": "State module first populate: official TRACER Schedule A donors only. Candidate/ballot and vote packages TBD.",
        },
        "state_filings": {
            "wired": True,
            "tracer_public": "https://tracer.sos.colorado.gov/",
            "tracer_data": LANDING,
            "donors": {
                "status": "sourced",
                "path": "/data/co/tracer-donors.json",
                "source_url": ZIP_URL,
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
        "sources": [
            {"url": ZIP_URL, "retrieved_at": retrieved},
            {"url": LANDING, "retrieved_at": retrieved},
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "tracer-donors.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT_DIR / 'tracer-donors.json'} rows={len(rows)} filers={len(by_candidate)} retrieved={retrieved}",
        flush=True,
    )


if __name__ == "__main__":
    build()
