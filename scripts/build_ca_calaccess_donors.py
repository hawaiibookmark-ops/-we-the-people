#!/usr/bin/env python3
"""Build California CAL-ACCESS Schedule A/C extract from official dbwebexport.zip."""

from __future__ import annotations

import csv
import json
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
ZIP_URL = "https://campaignfinance.cdn.sos.ca.gov/dbwebexport.zip"
LANDING = "https://www.sos.ca.gov/campaign-lobbying/helpful-resources/raw-data-campaign-finance-and-lobbying-activity"
RETRIEVED = "2026-09-02T11:23:29Z"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "ca"
STUB = ROOT / "public" / "data" / "ca.json"
WORK = Path("/tmp/ca-calaccess")
KEEP_FORMS = {"A", "A-1", "A1", "F401A", "C"}
SKIP_FORMS = {"I"}
YEARS = {2025, 2026}
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
    "ctrib_zip4",
    "adr1",
    "adr2",
}
POLICY = (
    "Official California CAL-ACCESS dbwebexport.zip RCPT_CD (Schedules A/C) only. "
    "Form types A, A-1, F401A, C; form I excluded. Receipt years 2025-2026. "
    "Latest AMEND_ID kept per filing line. Street addresses omitted. "
    "Names copied from the official file only and never invented. "
    "Donor lists are not sold. No Ballotpedia. No scores."
)


def text(val: str | None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def assembled_name(naml: str | None, namf: str | None, namt: str | None = None, nams: str | None = None) -> str | None:
    last = text(naml)
    first = text(namf)
    title = text(namt)
    suffix = text(nams)
    if not any((last, first, title, suffix)):
        return None
    given = " ".join(p for p in (title, first) if p)
    if given or suffix:
        after = " ".join(p for p in (given, suffix) if p)
        if last and after:
            return f"{last}, {after}"
        return last or after
    return last


def parse_date(raw: str | None) -> tuple[str | None, int | None]:
    s = text(raw)
    if not s:
        return None, None
    # 1/20/2025 12:00:00 AM  or  2025-01-20
    if s[0:4].isdigit() and s[4:5] == "-":
        return s[:10], int(s[:4])
    parts = s.split()[0].split("/")
    if len(parts) != 3:
        return None, None
    try:
        m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{y:04d}-{m:02d}-{d:02d}", y
    except ValueError:
        return None, None


def parse_amount(raw: str | None) -> float | None:
    s = text(raw)
    if not s:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def parse_amend(raw: str | None) -> int:
    s = text(raw)
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def ensure_export() -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    zpath = WORK / "dbwebexport.zip"
    if not zpath.exists() or zpath.stat().st_size < 1_000_000:
        subprocess.check_call(["curl", "-fsSL", "-A", UA, "-o", str(zpath), ZIP_URL])
    data = WORK / "CalAccess" / "DATA"
    needed = ["RCPT_CD.TSV", "FILERNAME_CD.TSV", "FILER_FILINGS_CD.TSV"]
    if not all((data / n).exists() for n in needed):
        subprocess.check_call(
            ["unzip", "-o", str(zpath), *[f"CalAccess/DATA/{n}" for n in needed], "-d", str(WORK)]
        )
    return data


def load_filer_names(path: Path) -> dict[str, str]:
    best: dict[str, tuple[str, str, str]] = {}
    with path.open("r", encoding="latin-1", errors="replace", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            fid = text(row.get("FILER_ID"))
            if not fid:
                continue
            name = assembled_name(row.get("NAML"), row.get("NAMF"), row.get("NAMT"), row.get("NAMS"))
            if not name:
                continue
            effect = text(row.get("EFFECT_DT")) or ""
            status = (text(row.get("STATUS")) or "").upper()
            prev = best.get(fid)
            if prev is None or (effect, status == "ACTIVE", name) > (prev[0], prev[1] == "ACTIVE", prev[2]):
                best[fid] = (effect, status, name)
    return {fid: rec[2] for fid, rec in best.items()}


def load_filing_to_filer(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open("r", encoding="latin-1", errors="replace", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            filing = text(row.get("FILING_ID"))
            filer = text(row.get("FILER_ID"))
            if filing and filer and filing not in mapping:
                mapping[filing] = filer
    return mapping


def slim_item(row: dict) -> dict:
    iso, _ = parse_date(row.get("RCPT_DATE"))
    item = {
        "contributor_name": assembled_name(
            row.get("CTRIB_NAML"),
            row.get("CTRIB_NAMF"),
            row.get("CTRIB_NAMT"),
            row.get("CTRIB_NAMS"),
        ),
        "contributor_type": text(row.get("ENTITY_CD")),
        "amount": parse_amount(row.get("AMOUNT")),
        "date": iso,
        "city": text(row.get("CTRIB_CITY")),
        "state": text(row.get("CTRIB_ST")),
        "form_type": text(row.get("FORM_TYPE")),
        "employer": text(row.get("CTRIB_EMP")),
        "occupation": text(row.get("CTRIB_OCC")),
    }
    if STREET_KEYS & {k.lower() for k in item}:
        raise RuntimeError("street/zip field leaked into slim item")
    return item


def scan_receipts(path: Path) -> list[dict]:
    # Keep latest AMEND_ID per (FILING_ID, LINE_ITEM) among year+form matches.
    best: dict[tuple[str, str], tuple[int, dict]] = {}
    kept = 0
    with path.open("r", encoding="latin-1", errors="replace", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(r, 1):
            form = text(row.get("FORM_TYPE")) or ""
            if form in SKIP_FORMS or form not in KEEP_FORMS:
                continue
            _, year = parse_date(row.get("RCPT_DATE"))
            if year not in YEARS:
                continue
            filing = text(row.get("FILING_ID"))
            line = text(row.get("LINE_ITEM"))
            if not filing or not line:
                continue
            amend = parse_amend(row.get("AMEND_ID"))
            key = (filing, line)
            prev = best.get(key)
            if prev is None or amend >= prev[0]:
                slim = {
                    "FILING_ID": filing,
                    "LINE_ITEM": line,
                    "AMEND_ID": str(amend),
                    "FORM_TYPE": form,
                    "TRAN_ID": text(row.get("TRAN_ID")),
                    "ENTITY_CD": text(row.get("ENTITY_CD")),
                    "CTRIB_NAML": text(row.get("CTRIB_NAML")),
                    "CTRIB_NAMF": text(row.get("CTRIB_NAMF")),
                    "CTRIB_NAMT": text(row.get("CTRIB_NAMT")),
                    "CTRIB_NAMS": text(row.get("CTRIB_NAMS")),
                    "CTRIB_CITY": text(row.get("CTRIB_CITY")),
                    "CTRIB_ST": text(row.get("CTRIB_ST")),
                    "CTRIB_EMP": text(row.get("CTRIB_EMP")),
                    "CTRIB_OCC": text(row.get("CTRIB_OCC")),
                    "RCPT_DATE": text(row.get("RCPT_DATE")),
                    "AMOUNT": text(row.get("AMOUNT")),
                }
                best[key] = (amend, slim)
            kept += 1
            if i % 2_000_000 == 0:
                print(f"  scanned {i} RCPT rows, year/form matches {kept}", flush=True)
    print(f"  RCPT year/form matches {kept}; after latest AMEND_ID {len(best)}", flush=True)
    return [rec for _, rec in best.values()]


def pick_meta(rows: list[dict], key: str) -> str | None:
    counts: dict[str, int] = {}
    for row in rows:
        val = text(row.get(key))
        if not val:
            continue
        counts[val] = counts.get(val, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def merge_ca_stub(row_count: int, filer_count: int) -> None:
    if STUB.exists():
        stub = json.loads(STUB.read_text(encoding="utf-8"))
    else:
        stub = {
            "election": {
                "jurisdiction": "California",
                "state_code": "CA",
                "general_date": "2026-11-03",
            },
            "state_filings": {},
            "nominees": {},
            "geo_by_zip": {},
            "sources": [],
        }
    election = stub.get("election") if isinstance(stub.get("election"), dict) else {}
    election.setdefault("jurisdiction", "California")
    election.setdefault("state_code", "CA")
    election.setdefault("general_date", "2026-11-03")
    election["note"] = (
        "Official SOS certified list, Clerk/LIS federal votes, and CAL-ACCESS RCPT "
        "(Schedules A/C) donors. Donor lists are not sold."
    )
    stub["election"] = election
    filings = stub.get("state_filings") if isinstance(stub.get("state_filings"), dict) else {}
    filings["wired"] = True
    filings["calaccess_public"] = "https://cal-access.sos.ca.gov/"
    filings["calaccess_data"] = LANDING
    filings["donors"] = {
        "status": "sourced",
        "path": "/data/ca/calaccess-donors.json",
        "source_url": ZIP_URL,
        "landing_url": LANDING,
        "retrieved_at": RETRIEVED,
        "counts": {
            "rows": row_count,
            "filers": filer_count,
            "items_per_filer_cap": 25,
            "receipt_years": [2025, 2026],
        },
        "do_not_sell_donor_lists": True,
    }
    stub["state_filings"] = filings
    sources = stub.get("sources") if isinstance(stub.get("sources"), list) else []
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {
            "url": ZIP_URL,
            "retrieved_at": RETRIEVED,
            "note": "CAL-ACCESS dbwebexport.zip → RCPT_CD.TSV",
        },
        {
            "url": LANDING,
            "retrieved_at": RETRIEVED,
            "note": "SOS raw data landing",
        },
    ]
    for s in extra:
        if s["url"] not in have:
            sources.append(s)
    stub["sources"] = sources
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    data = ensure_export()
    print("loading FILERNAME_CD", flush=True)
    filer_names = load_filer_names(data / "FILERNAME_CD.TSV")
    print(f"  filer names {len(filer_names)}", flush=True)
    print("loading FILER_FILINGS_CD", flush=True)
    filing_to_filer = load_filing_to_filer(data / "FILER_FILINGS_CD.TSV")
    print(f"  filings {len(filing_to_filer)}", flush=True)
    print("scanning RCPT_CD", flush=True)
    rows = scan_receipts(data / "RCPT_CD.TSV")

    grouped: dict[str, list[dict]] = defaultdict(list)
    unknown = 0
    for row in rows:
        filer_id = filing_to_filer.get(text(row.get("FILING_ID")) or "")
        name = filer_names.get(filer_id or "") if filer_id else None
        if not name:
            name = filer_id
        if not name:
            unknown += 1
            continue
        row["_filer_id"] = filer_id
        grouped[name].append(row)
    print(f"  grouped filers={len(grouped)} unmatched_filing={unknown}", flush=True)

    by_candidate: dict[str, dict] = {}
    for name in sorted(grouped):
        filer_rows = grouped[name]
        ranked = sorted(
            filer_rows,
            key=lambda r: (
                parse_amount(r.get("AMOUNT")) is None,
                -(parse_amount(r.get("AMOUNT")) or 0.0),
                parse_date(r.get("RCPT_DATE"))[0] or "",
                text(r.get("TRAN_ID")) or "",
            ),
        )
        by_candidate[name] = {
            "candidate_name": name,
            "calaccess_filer_name": name,
            "filer_id": pick_meta(filer_rows, "_filer_id"),
            "matched_to_site": False,
            "status": "unmatched_no_roster",
            "item_count_all": len(filer_rows),
            "items": [slim_item(r) for r in ranked[:25]],
        }

    payload = {
        "policy": POLICY,
        "by_candidate": by_candidate,
        "retrieved_at": RETRIEVED,
        "source_url": ZIP_URL,
        "landing_url": LANDING,
        "attribution": "California Secretary of State CAL-ACCESS",
        "row_count": len(rows),
        "filer_count": len(by_candidate),
        "counts": {
            "rows": len(rows),
            "filers": len(by_candidate),
            "items_per_filer_cap": 25,
            "receipt_years": [2025, 2026],
        },
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
        "scope": "California CAL-ACCESS RCPT 2025-2026 (A/A-1/F401A/C). Top 25 contributions per filer by amount.",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "calaccess-donors.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    merge_ca_stub(len(rows), len(by_candidate))
    print(f"Wrote {dest} rows={len(rows)} filers={len(by_candidate)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
