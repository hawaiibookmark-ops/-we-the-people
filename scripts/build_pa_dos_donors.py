#!/usr/bin/env python3
"""Official Pennsylvania DOS 2026 Full Export contribution extract (Schedule A-style)."""

from __future__ import annotations

import csv
import heapq
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(8_000_000)

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T16:08:35Z"
ZIP_URL = (
    "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/"
    "campaign-finance/campaign-finance-data/2026.zip"
)
LANDING = "https://www.pa.gov/agencies/dos/resources/voting-and-elections-resources/campaign-finance-data"
README = (
    "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/"
    "campaign-finance/campaign-finance-data/readme-cf-data.txt"
)
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "pa"
STUB = ROOT / "public" / "data" / "pa.json"
CACHE = Path("/tmp/pa-dos/2026.zip")
CAP = 25
EXPECT_ROWS = 375_604
EXPECT_FILERS = 1_239
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
    "Official Pennsylvania Department of State 2026 Full Campaign Finance Export "
    "(contrib_2026.txt). One row per official contribution-file record. "
    "Filers are grouped by official FilerID (1,239 distinct IDs in contrib_2026.txt). "
    "Committee name is the latest FILERNAME from filer_2026.txt when present. "
    "Street addresses and ZIP omitted. Occupation kept when present on the official "
    "row. Names copied from the official file only and never invented. Donor lists "
    "are not sold. No Ballotpedia. No scores."
)


def fetch_zip() -> Path:
    if CACHE.exists() and CACHE.stat().st_size > 1_000_000:
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    req = Request(ZIP_URL, headers={"User-Agent": UA, "Accept": "application/zip,*/*"})
    with urlopen(req, timeout=180) as resp:
        CACHE.write_bytes(resp.read())
    return CACHE


def zip_text(zf: zipfile.ZipFile, name: str) -> str:
    raw = zf.read(name)
    return raw.decode("latin-1")


def fid(row: dict) -> str:
    return (row.get("FILERID") or row.get("FilerID") or "").strip().strip('"')


def latest_filers(rows: list[dict]) -> dict[str, dict]:
    by_id: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        i = fid(row)
        if i:
            by_id[i].append(row)
    out = {}
    for i, recs in by_id.items():
        out[i] = max(
            recs,
            key=lambda r: (
                (r.get("SubmittedDate") or ""),
                int(r.get("CYCLE") or 0),
                r.get("CampaignfinanceID") or r.get("CampaignFinanceID") or "",
            ),
        )
    return out


def parse_amount(row: dict) -> float | None:
    for key in ("CONTAMT1", "CONTAMT2", "CONTAMT3"):
        raw = (row.get(key) or "").strip()
        if not raw or raw in {"0", "0.0", "0.00"}:
            continue
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            continue
    raw = (row.get("CONTAMT1") or "").strip()
    if not raw:
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def parse_date(row: dict) -> str | None:
    for key in ("CONTDATE1", "CONTDATE2", "CONTDATE3"):
        raw = (row.get(key) or "").strip()
        if not raw or raw in {"0", "0.0"}:
            continue
        digits = "".join(c for c in raw if c.isdigit())
        if len(digits) == 8:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
        if len(raw) >= 10 and raw[4] == "-":
            return raw[:10]
        return raw
    return None


def slim_item(row: dict) -> dict:
    name = (row.get("CONTRIBUTOR") or "").strip()
    if not name:
        raise SystemExit("PA DOS contrib row missing official CONTRIBUTOR")
    item = {
        "contributor_name": name,
        "amount": parse_amount(row),
        "date": parse_date(row),
        "city": (row.get("CITY") or "").strip() or None,
        "state": (row.get("STATE") or "").strip() or None,
        "occupation": (row.get("OCCUPATION") or "").strip() or None,
        "employer": (row.get("ENAME") or "").strip() or None,
        "retrieved_at": RETRIEVED,
        "source_url": ZIP_URL,
    }
    if STREET_KEYS & {k.lower() for k in item}:
        raise SystemExit("street field leaked into PA DOS slim item")
    return item


def write_stub(payload: dict) -> None:
    stub = json.loads(STUB.read_text(encoding="utf-8")) if STUB.exists() else {}
    if stub.get("candidates_path"):
        raise SystemExit("refusing to claim PA candidates_path; ballots are not cleared")
    filings = stub.setdefault("state_filings", {})
    existing = (filings.get("donors") or {}).copy()
    if existing.get("path") == "/data/pa/fec-donors.json" or existing.get("status") == "partial":
        filings["federal_fec"] = {
            "status": "partial",
            "path": "/data/pa/fec-donors.json",
            "scope": (
                "Pennsylvania 2026 House/Senate federal FEC Schedule A $200+ only. "
                "State DOS 2026 Full Export is a separate sourced extract."
            ),
            "source_url": existing.get("source_url")
            or "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip",
            "retrieved_at": existing.get("retrieved_at") or "2026-09-02T15:58:08Z",
            "counts": existing.get("counts") or {},
            "do_not_sell_donor_lists": True,
        }
    if filings.get("federal_fec", {}).get("path") != "/data/pa/fec-donors.json":
        raise SystemExit("refusing to wipe PA FEC partial extract")
    if (OUT_DIR / "fec-donors.json").exists():
        fec = json.loads((OUT_DIR / "fec-donors.json").read_text(encoding="utf-8"))
        if fec.get("row_count") != 30261 or fec.get("candidate_count") != 114:
            raise SystemExit("PA FEC extract counts changed; refusing to proceed")
    filings["wired"] = True
    filings["dos_export"] = ZIP_URL
    filings["dos_landing"] = LANDING
    filings.pop("state_donors", None)
    filings["donors"] = {
        "status": "sourced",
        "path": "/data/pa/dos-donors.json",
        "source_url": ZIP_URL,
        "retrieved_at": RETRIEVED,
        "counts": payload["counts"],
        "do_not_sell_donor_lists": True,
    }
    stub["election"] = {
        "jurisdiction": "Pennsylvania",
        "state_code": "PA",
        "general_date": "2026-11-03",
        "note": (
            "Official Pennsylvania DOS 2026 Full Export Schedule A-style contributions, "
            "Clerk/LIS federal votes, and federal FEC Schedule A $200+. "
            "State ballots are pending until official lists clear. Donor lists are not sold."
        ),
    }
    stub["votes_path"] = "/data/pa/votes.json"
    stub["congress_delegation_path"] = "/data/pa/congress-delegation.json"
    stub["legislature_vote_index_path"] = "/data/pa/legislature-vote-index.json"
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    stub.pop("candidates_path", None)
    stub.pop("candidate_summary_path", None)
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": ZIP_URL, "retrieved_at": RETRIEVED, "note": "Official PA DOS 2026 Full Campaign Finance Export"},
        {"url": LANDING, "retrieved_at": RETRIEVED, "note": "PA DOS campaign-finance data landing"},
        {"url": README, "retrieved_at": RETRIEVED, "note": "PA DOS campaign-finance export layout"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    zpath = fetch_zip()
    with zipfile.ZipFile(zpath) as zf:
        contrib = list(csv.DictReader(io.StringIO(zip_text(zf, "contrib_2026.txt"))))
        filers = list(csv.DictReader(io.StringIO(zip_text(zf, "filer_2026.txt"))))
    latest = latest_filers(filers)
    heaps: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    meta: dict[str, dict] = {}
    seq = 0
    for row in contrib:
        filer_id = fid(row)
        if not filer_id:
            continue
        key = filer_id
        item = slim_item(row)
        counts[key] += 1
        rec = latest.get(filer_id) or {}
        meta.setdefault(
            key,
            {
                "committee_name": (rec.get("FILERNAME") or "").strip() or filer_id,
                "filer_id": filer_id,
                "filer_type": (rec.get("FILERTYPE") or "").strip() or None,
                "office": (rec.get("OFFICE") or "").strip() or None,
                "district": (rec.get("DISTRICT") or "").strip() or None,
                "party": (rec.get("PARTY") or "").strip() or None,
            },
        )
        heap_key = (item["amount"] if item["amount"] is not None else float("-inf"), item.get("date") or "", seq)
        seq += 1
        entry = (heap_key, item)
        if len(heaps[key]) < CAP:
            heapq.heappush(heaps[key], entry)
        elif heap_key > heaps[key][0][0]:
            heapq.heapreplace(heaps[key], entry)
    row_count = sum(counts.values())
    if row_count != EXPECT_ROWS or len(counts) != EXPECT_FILERS:
        raise SystemExit(f"PA DOS expected {EXPECT_ROWS}/{EXPECT_FILERS}, got {row_count}/{len(counts)}")
    by_candidate = {}
    for key in sorted(counts):
        items = [
            item
            for _k, item in sorted(
                heaps[key],
                key=lambda kv: (
                    kv[0][0] == float("-inf"),
                    -kv[0][0] if kv[0][0] != float("-inf") else 0.0,
                    kv[0][1],
                    kv[0][2],
                ),
            )
        ]
        info = meta[key]
        by_candidate[key] = {
            **info,
            "status": "unmatched_no_roster",
            "matched_to_site": False,
            "item_count_all": counts[key],
            "items": items,
        }
    payload = {
        "policy": POLICY,
        "source_url": ZIP_URL,
        "landing_url": LANDING,
        "layout_url": README,
        "retrieved_at": RETRIEVED,
        "row_count": row_count,
        "filer_count": len(by_candidate),
        "counts": {
            "rows": row_count,
            "filers": len(by_candidate),
            "items_per_filer_cap": CAP,
            "election_year": 2026,
        },
        "by_candidate": by_candidate,
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
        "scope": (
            "Pennsylvania DOS 2026 Full Export contrib_2026.txt. Federal FEC Schedule A "
            "is a separate partial extract. Streets omitted. Donor lists are not sold."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "dos-donors.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    write_stub(payload)
    print(f"wrote {dest} rows={row_count} filers={len(by_candidate)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
