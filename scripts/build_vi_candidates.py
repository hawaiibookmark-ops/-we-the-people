#!/usr/bin/env python3
"""Official US Virgin Islands 2026 candidate lists (ESVI + FEC Delegate).

166 rows: June official 88 + August general 70 + FEC Delegate 8.
Prefer August general for November. No US Senate. Streets omitted.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-03T13:54:09Z"
FEC_CN = "https://www.fec.gov/files/bulk-downloads/2026/cn26.zip"
LANDING_GEN = "https://vivote.gov/?elections=2026-general-election"
LANDING_PRI = "https://vivote.gov/?elections=2026-primary-election"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "vi"
STUB = ROOT / "public" / "data" / "vi.json"
CACHE = Path("/tmp/vi-official")
PACKAGE = Path("/workspace/wtp-live-data/50state/2026-09-03-vi/VI/package")
EXPECT_JUNE = 88
EXPECT_AUG = 70
EXPECT_FEC = 8
EXPECT = 166

# Official ESVI PDFs (Supervisor of Elections Caroline F. Fawkes).
PDFS = (
    {
        "key": "june-stx",
        "url": "https://vivote.gov/wp-content/uploads/2026/06/2026-Election-Public-Offices-Aspirant-Listing-STX-OFFICIAL-June-2026.pdf",
        "list_kind": "official_june",
        "election": "2026 Official June Candidate Listing (Primary and General)",
        "election_date": "2026-06-17",
        "district": "STX",
        "district_name": "St. Croix",
        "expect": 45,
    },
    {
        "key": "june-stt",
        "url": "https://vivote.gov/wp-content/uploads/2026/06/2026-Election-Public-Offices-Aspirant-Listing-STT-STJ-OFFICIAL-June-2026.pdf",
        "list_kind": "official_june",
        "election": "2026 Official June Candidate Listing (Primary and General)",
        "election_date": "2026-06-17",
        "district": "STTJ",
        "district_name": "St. Thomas/St. John",
        "expect": 43,
    },
    {
        "key": "aug-stx",
        "url": "https://vivote.gov/wp-content/uploads/2026/08/2026-Election-Public-Offices-Aspirant-Listing-STX-OFFICIAL-August-2026.pdf",
        "list_kind": "official_august",
        "election": "2026 General Election",
        "election_date": "2026-11-03",
        "district": "STX",
        "district_name": "St. Croix",
        "expect": 38,
    },
    {
        "key": "aug-stt",
        "url": "https://vivote.gov/wp-content/uploads/2026/08/2026-General-Election-Official-Listing-of-Candidates-St.-Thomas-and-St.-John-District-8.19.2026.pdf",
        "list_kind": "official_august",
        "election": "2026 General Election",
        "election_date": "2026-11-03",
        "district": "STTJ",
        "district_name": "St. Thomas/St. John",
        "expect": 32,
    },
)

PARTY_RE = re.compile(r"\b(Democrat|Independent|Republican|ICM)\b")
ROW_RE = re.compile(r"^\s*(\d{1,2})\s+(.+)$")
ADDR_RE = re.compile(
    r"\s+(?:P\.?O\.?\s*(?:Box|\d)|(?:\d{3,}(?:-\d+)?)\s)",
    re.I,
)
OFFICES = (
    ("Delegate to Congress", "Delegate to Congress", True),
    ("Governor/Lt. Governor", "Governor/Lt. Governor", True),
    ("Legislature (At Large)", "Legislature At Large", True),
    ("Legislature of the VI", "Legislature", False),
    ("Senator (Legislature)", "Legislature", False),
    ("Senator(Legislature)", "Legislature", False),
    ("Board of Education", "Board of Education", False),
    ("Board of Elections", "Board of Elections", False),
)
FEC_PARTY = {"DEM": "Democrat", "REP": "Republican", "IND": "Independent"}
STREET_KEYS = {"street", "address", "addr", "mailing_address", "email", "phone", "telephone"}
PRESERVE = (
    "public/data/csc-donors.json",
    "public/data/hawaii.json",
    "public/data/hawaii-votes.json",
    "public/data/congress-votes.json",
    "public/data/donors.json",
    "public/data/ny/candidates.json",
    "public/data/ny.json",
    "public/data/nj/candidates.json",
    "public/data/oh/candidates.json",
    "public/data/il/sbe-donors.json",
    "public/data/tx/tec-donors.json",
    "public/data/federal.json",
)


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def snapshot() -> dict[str, str]:
    out = {}
    for rel in PRESERVE:
        p = ROOT / rel
        if p.exists():
            out[rel] = sha1(p)
    return out


def assert_preserved(before: dict[str, str]) -> None:
    after = snapshot()
    for rel, digest in before.items():
        got = after.get(rel)
        if got != digest:
            raise SystemExit(f"refusing to wipe {rel}: {digest} -> {got}")


def from_package() -> list[dict] | None:
    if not PACKAGE.is_dir():
        return None
    for name in ("candidates.json", "vi-candidates.json"):
        dest = PACKAGE / name
        if dest.exists():
            payload = json.loads(dest.read_text(encoding="utf-8"))
            if isinstance(payload, list) and len(payload) == EXPECT:
                return payload
            if isinstance(payload, dict):
                rows = payload.get("candidates") or payload.get("rows")
                if isinstance(rows, list) and len(rows) == EXPECT:
                    return rows
    return None


def fetch_pdf(spec: dict) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"{spec['key']}.pdf"
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest
    subprocess.check_call(
        ["curl", "-fsSL", "-A", UA, "--max-time", "90", "-o", str(dest), spec["url"]]
    )
    return dest


def pdf_text(pdf: Path) -> str:
    txt = pdf.with_suffix(".txt")
    if not txt.exists() or txt.stat().st_size < 100:
        subprocess.check_call(["pdftotext", "-layout", str(pdf), str(txt)])
    return txt.read_text(encoding="utf-8", errors="replace")


def office_of(blob: str) -> tuple[str, bool] | None:
    for raw, canon, territory in OFFICES:
        if raw in blob:
            return canon, territory
    return None


def parse_pdf(spec: dict) -> list[dict]:
    text = pdf_text(fetch_pdf(spec))
    rows: list[dict] = []
    seen_n: set[int] = set()
    for raw in text.splitlines():
        m = ROW_RE.match(raw)
        if not m:
            continue
        n = int(m.group(1))
        rest = m.group(2).strip()
        if n < 1 or n > 50 or n in seen_n:
            continue
        if rest.upper().startswith("NAME OF CANDIDATE") or rest.upper().startswith("LISTING"):
            continue
        pm = PARTY_RE.search(rest)
        if not pm:
            continue
        name_addr = rest[: pm.start()].strip()
        after = rest[pm.end() :]
        office_hit = office_of(after)
        if not office_hit:
            continue
        office, territory = office_hit
        am = ADDR_RE.search(name_addr)
        name = name_addr[: am.start()].strip() if am else name_addr
        name = re.sub(r"\s+", " ", name).strip(" ,")
        if not name or name.lower() in {"name of candidate", "no."}:
            continue
        seen_n.add(n)
        district = None if territory else spec["district"]
        rows.append(
            {
                "state": "VI",
                "contest_key": f"VI|{office}|{district or ''}|",
                "office": office,
                "district": district,
                "district_name": None if territory else spec["district_name"],
                "candidate_office": office,
                "party": pm.group(1),
                "candidate_name": name,
                "list_kind": spec["list_kind"],
                "election": spec["election"],
                "election_year": "2026",
                "election_date": spec["election_date"],
                "complete": True,
                "certified": True,
                "source_url": spec["url"],
                "retrieved_at": RETRIEVED,
            }
        )
    if len(rows) != spec["expect"]:
        raise SystemExit(f"{spec['key']} rows {len(rows)} != {spec['expect']}: {[r['candidate_name'] for r in rows]}")
    return rows


def fec_cn_path() -> Path:
    for cand in (Path("/tmp/fec/cn26.zip"), Path("/tmp/fec-fresh/cn26.zip"), CACHE / "cn26.zip"):
        if cand.exists() and cand.stat().st_size > 1000:
            return cand
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / "cn26.zip"
    subprocess.check_call(["curl", "-fsSL", "-A", UA, "--max-time", "90", "-o", str(dest), FEC_CN])
    return dest


def fec_delegate_rows() -> list[dict]:
    zpath = fec_cn_path()
    with zipfile.ZipFile(zpath) as zf:
        name = zf.namelist()[0]
        raw = zf.read(name).decode("latin-1")
    rows: list[dict] = []
    for ln in raw.splitlines():
        parts = ln.split("|")
        if len(parts) < 15:
            continue
        cand_id, cand_name, pty, year, st, office, dist, ici, status = parts[:9]
        if st != "VI" or office != "H" or year != "2026":
            continue
        rows.append(
            {
                "state": "VI",
                "contest_key": "VI|Delegate to Congress||",
                "office": "Delegate to Congress",
                "district": None,
                "district_name": None,
                "candidate_office": "Delegate to Congress",
                "party": FEC_PARTY.get(pty, pty),
                "candidate_name": cand_name,
                "list_kind": "fec_delegate",
                "election": "2026 Federal Delegate",
                "election_year": "2026",
                "election_date": "2026-11-03",
                "complete": True,
                "certified": False,
                "federal_only": True,
                "cand_id": cand_id,
                "source_url": FEC_CN,
                "retrieved_at": RETRIEVED,
            }
        )
    rows.sort(key=lambda r: r["cand_id"])
    if len(rows) != EXPECT_FEC:
        raise SystemExit(f"FEC VI Delegate rows {len(rows)} != {EXPECT_FEC}: {rows}")
    return rows


def write_stub(rows: list[dict]) -> None:
    stub: dict = {}
    if STUB.exists():
        stub = json.loads(STUB.read_text(encoding="utf-8"))
        donors = ((stub.get("state_filings") or {}).get("donors") or {})
        if donors.get("status") == "sourced" and donors.get("path"):
            raise SystemExit("refusing to wipe sourced VI state donors")
    kinds = Counter(r["list_kind"] for r in rows)
    stub["election"] = {
        "jurisdiction": "U.S. Virgin Islands",
        "state_code": "VI",
        "general_date": "2026-11-03",
        "primary_date": "2026-08-01",
        "note": (
            "Official Election System of the Virgin Islands June candidate listings "
            "(88 rows) plus August general listing (70 rows) and FEC 2026 Delegate "
            "master (8 rows). Prefer August general for November. No U.S. Senate; "
            "Delegate is the only federal office. Streets omitted. Donor lists are not sold."
        ),
        "prefer_for_november": "official_august",
        "no_us_senate": True,
        "federal_offices": ["Delegate to Congress"],
    }
    stub["nominees"] = {}
    stub["geo_by_zip"] = {}
    stub["sources"] = [
        {"url": LANDING_PRI, "retrieved_at": RETRIEVED, "note": "ESVI 2026 Primary Election official candidate PDFs"},
        {"url": LANDING_GEN, "retrieved_at": RETRIEVED, "note": "ESVI 2026 General Election official candidate PDFs (prefer for November)"},
        {"url": FEC_CN, "retrieved_at": RETRIEVED, "note": "FEC candidate master — VI Delegate only (no Senate)"},
    ]
    for spec in PDFS:
        stub["sources"].append(
            {
                "url": spec["url"],
                "retrieved_at": RETRIEVED,
                "note": f"Official ESVI {spec['list_kind']} {spec['district_name']}",
            }
        )
    stub["state_filings"] = {
        "wired": True,
        "donors": {
            "status": "pending",
            "reason": "Virgin Islands campaign-finance bulk is not extracted in this populate. Donor names are not invented.",
            "do_not_sell_donor_lists": True,
        },
        "candidates": {
            "status": "sourced",
            "path": "/data/vi/candidates.json",
            "source_url": LANDING_GEN,
            "retrieved_at": RETRIEVED,
            "complete": True,
            "prefer_for_november": "official_august",
            "no_us_senate": True,
            "federal_offices": ["Delegate to Congress"],
            "counts": {
                "rows": len(rows),
                "june": kinds.get("official_june", 0),
                "august": kinds.get("official_august", 0),
                "fec_delegate": kinds.get("fec_delegate", 0),
                "contest_keys": len({r["contest_key"] for r in rows}),
            },
            "streets_omitted": True,
            "do_not_sell_donor_lists": True,
        },
        "esvi_primary": LANDING_PRI,
        "esvi_general": LANDING_GEN,
    }
    stub["candidates_path"] = "/data/vi/candidates.json"
    stub["candidate_summary_path"] = "/data/vi/candidate-summary.json"
    stub.pop("votes_path", None)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(rows: list[dict]) -> None:
    kinds = Counter(r.get("list_kind") for r in rows)
    if len(rows) != EXPECT:
        raise SystemExit(f"VI candidates {len(rows)} != {EXPECT}")
    if kinds.get("official_june") != EXPECT_JUNE or kinds.get("official_august") != EXPECT_AUG or kinds.get("fec_delegate") != EXPECT_FEC:
        raise SystemExit(f"VI list_kind split {dict(kinds)} != {EXPECT_JUNE}/{EXPECT_AUG}/{EXPECT_FEC}")
    if any("senate" in (r.get("office") or "").lower() for r in rows):
        raise SystemExit("VI must not invent a U.S. Senate contest")
    if any(k.lower() in STREET_KEYS for r in rows for k in r):
        raise SystemExit("VI candidates must omit streets/email/phone")
    if any(r.get("complete") is not True for r in rows):
        raise SystemExit("VI candidates must be complete=true")
    if any(r.get("retrieved_at") != RETRIEVED for r in rows):
        raise SystemExit("VI retrieved_at must be 2026-09-03T13:54:09Z")
    if any("ballotpedia" in (r.get("source_url") or "").lower() for r in rows):
        raise SystemExit("VI must not use Ballotpedia")
    if not any(r.get("candidate_name") == "Janelle K. Sarauw" and r.get("list_kind") == "official_august" for r in rows):
        raise SystemExit("August general missing Janelle K. Sarauw")
    if not any(r.get("cand_id") == "H2VI00082" for r in rows):
        raise SystemExit("FEC Delegate missing PLASKETT H2VI00082")


def main() -> int:
    before = snapshot()
    rows = from_package()
    if rows is None:
        rows = []
        for spec in PDFS:
            rows.extend(parse_pdf(spec))
        rows.extend(fec_delegate_rows())
    validate(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    kinds = Counter(r["list_kind"] for r in rows)
    summary = {
        "row_count": len(rows),
        "contest_key_count": len({r["contest_key"] for r in rows}),
        "list_kind": sorted(kinds),
        "by_list_kind": dict(kinds),
        "complete": True,
        "certified": True,
        "prefer_for_november": "official_august",
        "no_us_senate": True,
        "federal_offices": ["Delegate to Congress"],
        "source_url": LANDING_GEN,
        "retrieved_at": RETRIEVED,
        "streets_omitted": True,
        "primary_certified": "2026-08-25",
        "primary_certification_source": "https://vivote.gov/2026-primary-election-certification/",
        "june_17_is_primary_certification": False,
        "note": (
            "Official ESVI June candidate listings (88) + August general (70) + FEC 2026 "
            "Delegate (8). Primary results certified August 25, 2026 (VIVOTE Special "
            "Notice), not June 17. Prefer August general for November. No U.S. Senate. "
            "Streets omitted. No Ballotpedia."
        ),
    }
    (OUT_DIR / "candidate-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_stub(rows)
    assert_preserved(before)
    print(
        f"wrote VI candidates {len(rows)} kinds={dict(kinds)} keys={summary['contest_key_count']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
