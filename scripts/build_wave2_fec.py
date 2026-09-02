#!/usr/bin/env python3
"""Wave-2 federal FEC Schedule A $200+ extracts (IL/MI/FL/NY/TX) from official indiv26 + cn26 + ccl26."""

from __future__ import annotations

import json
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T14:30:00Z"
INDIV_URL = "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip"
CN_URL = "https://www.fec.gov/files/bulk-downloads/2026/cn26.zip"
CCL_URL = "https://www.fec.gov/files/bulk-downloads/2026/ccl26.zip"
LAYOUT_URL = "https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
CACHE = Path("/tmp/fec")
FRESH = Path("/tmp/fec-fresh")
STATES = ("IL", "MI", "FL", "NY", "TX")
# Official live extract targets when previously published; others are recorded from this scan.
EXPECT = {
    "IL": {"candidates": 189, "kept_rows": 48312},
}


def fetch_zip(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 200:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/zip,*/*;q=0.8"})
    with urlopen(req, timeout=600) as resp:
        dest.write_bytes(resp.read())
    return dest


def pick_cn() -> Path:
    for p in (FRESH / "cn26.zip", CACHE / "cn26.zip"):
        if p.exists() and p.stat().st_size > 200:
            return p
    return fetch_zip(CN_URL, CACHE / "cn26.zip")


def pick_ccl() -> Path:
    for p in (FRESH / "ccl26.zip", CACHE / "ccl26.zip"):
        if p.exists() and p.stat().st_size > 200:
            return p
    return fetch_zip(CCL_URL, CACHE / "ccl26.zip")


def pick_indiv() -> Path:
    cached = CACHE / "indiv26.zip"
    if cached.exists() and cached.stat().st_size > 1_000_000:
        return cached
    return fetch_zip(INDIV_URL, cached)


def zip_text(path: Path, inner: str) -> str:
    with zipfile.ZipFile(path) as zf:
        name = inner if inner in zf.namelist() else next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        return zf.read(name).decode("utf-8", errors="replace")


def parse_cn(path: Path) -> dict[str, list[dict]]:
    by_state: dict[str, list[dict]] = {st: [] for st in STATES}
    for ln in zip_text(path, "cn.txt").splitlines():
        cols = ln.split("|")
        if len(cols) < 10:
            continue
        rec = {
            "candidate_id": cols[0].strip(),
            "candidate_name": cols[1].strip(),
            "party": cols[2].strip() or None,
            "election_year": cols[3].strip(),
            "office_state": cols[4].strip(),
            "office": cols[5].strip(),
            "district": (cols[6] or "").strip() or None,
            "candidate_status": cols[8].strip() or None,
            "committee_id": cols[9].strip() or None,
        }
        if rec["office_state"] not in by_state or rec["election_year"] != "2026":
            continue
        if rec["office"] not in {"H", "S"}:
            continue
        if not rec["candidate_id"]:
            raise SystemExit(f"cn26 missing official candidate id: {rec}")
        by_state[rec["office_state"]].append(rec)
    for st, rows in by_state.items():
        print(f"cn26 {st} H+S={len(rows)}", flush=True)
        exp = EXPECT.get(st)
        if exp and len(rows) != exp["candidates"]:
            raise SystemExit(f"expected {exp['candidates']} {st} cn26 rows, got {len(rows)}")
    return by_state


def pcc_owners(path: Path, cand_ids: set[str]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for ln in zip_text(path, "ccl.txt").splitlines():
        cols = ln.split("|")
        if len(cols) < 6:
            continue
        cand, cyr, _fyr, cmte, _tp, dsgn = [c.strip() for c in cols[:6]]
        if cand not in cand_ids or cyr != "2026" or dsgn != "P" or not cmte:
            continue
        prev = owners.get(cmte)
        if prev and prev != cand:
            owners[cmte] = min(prev, cand)
            continue
        owners[cmte] = cand
    return owners


def parse_date(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[4:8]}-{text[0:2]}-{text[2:4]}"
    return text


def slim_item(cols: list[str]) -> dict:
    image = (cols[4] or "").strip()
    item = {
        "contributor_name": (cols[7] or "").strip(),
        "amount": float(cols[14] or 0),
        "date": parse_date(cols[13]),
        "city": (cols[8] or "").strip() or None,
        "state": (cols[9] or "").strip() or None,
        "employer": (cols[11] or "").strip() or None,
        "image_number": image or None,
        "fec_url": f"https://docquery.fec.gov/cgi-bin/fecimg/?{image}" if image else None,
    }
    if not item["contributor_name"]:
        raise SystemExit("official NAME missing on kept Schedule A row")
    return item


def scan_indiv(path: Path, pccs: set[str]) -> dict[str, list[dict]]:
    by_cmte: dict[str, list[dict]] = defaultdict(list)
    n = 0
    with zipfile.ZipFile(path) as zf:
        with zf.open("itcont.txt") as fh:
            for raw in fh:
                n += 1
                if n % 4_000_000 == 0:
                    print(f"  scanned {n} itcont lines", flush=True)
                line = raw.decode("utf-8", errors="replace")
                cmte = line.split("|", 1)[0]
                if cmte not in pccs:
                    continue
                cols = line.rstrip("\n").split("|")
                if len(cols) < 19:
                    continue
                if (cols[18] or "").strip() == "X":
                    continue
                try:
                    amt = float(cols[14] or 0)
                except ValueError:
                    continue
                if amt < 200:
                    continue
                by_cmte[cmte].append(slim_item(cols))
    print(f"scanned {n} itcont lines; kept {sum(len(v) for v in by_cmte.values())}", flush=True)
    return by_cmte


def rank(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda it: (
            -(it.get("amount") or 0),
            it.get("date") or "",
            it.get("image_number") or "",
            it.get("contributor_name") or "",
        ),
    )


STATE_SCOPE = {
    "IL": "Illinois 2026 House/Senate federal FEC Schedule A $200+ only. State SBE Schedule A is a separate sourced extract.",
    "MI": "Michigan 2026 House/Senate federal FEC Schedule A $200+ only. State MiTN Schedule A is a separate sourced extract.",
    "FL": (
        "Florida 2026 House/Senate federal FEC Schedule A $200+ only. "
        "State campaign-finance bulk is blocked (no standing statewide bulk URL; form-limited)."
    ),
    "NY": "New York 2026 House/Senate federal FEC Schedule A $200+ only. State NYSBOE filings are a separate extract when present.",
    "TX": "Texas 2026 House/Senate federal FEC Schedule A $200+ only. State TEC filings are a separate extract when present.",
}


def build_payload(state: str, cands: list[dict], owners: dict[str, str], by_cmte: dict[str, list[dict]]) -> dict:
    by_candidate: dict[str, dict] = {}
    kept_unique = 0
    with_receipts = 0
    for rec in sorted(cands, key=lambda r: r["candidate_id"]):
        pcc = rec["committee_id"]
        owner = owners.get(pcc) if pcc else None
        if pcc and owner and owner != rec["candidate_id"]:
            items_all: list[dict] = []
            status = "empty"
            reason = (
                f"cn26 CAND_PCC {pcc} is linked in ccl26 (CMTE_DSGN=P) to {owner} only. "
                "Receipts are not duplicated onto this candidacy."
            )
            committee_id = pcc
        elif not pcc:
            items_all = []
            status = "empty"
            reason = "No principal campaign committee on FEC candidate master (cn26). Honest-empty. Joint fundraising committees are not used."
            committee_id = None
        else:
            items_all = rank(by_cmte.get(pcc, []))
            committee_id = pcc
            if items_all:
                status = "ok"
                reason = None
                kept_unique += len(items_all)
                with_receipts += 1
            else:
                status = "empty"
                reason = (
                    f"Principal campaign committee {pcc} has no Schedule A individual receipts "
                    "of $200+ in indiv26 (MEMO_CD=X skipped)."
                )
        by_candidate[rec["candidate_id"]] = {
            "candidate_id": rec["candidate_id"],
            "candidate_name": rec["candidate_name"] or None,
            "office": rec["office"],
            "district": rec["district"],
            "party": rec["party"],
            "committee_id": committee_id,
            "status": status,
            "reason": reason,
            "item_count_all": len(items_all),
            "items": items_all[:25],
            "retrieved_at": RETRIEVED,
            "source_url": INDIV_URL,
        }
    empty = sum(1 for v in by_candidate.values() if v["status"] == "empty")
    exp = EXPECT.get(state)
    if exp and (len(by_candidate) != exp["candidates"] or kept_unique != exp["kept_rows"]):
        raise SystemExit(
            f"{state} expected {exp['candidates']}/{exp['kept_rows']}, "
            f"got cands={len(by_candidate)} kept={kept_unique}"
        )
    policy = (
        "Official FEC bulk Schedule A individual receipts of $200+ from indiv26.zip "
        f"(plus cn26 for CAND_PCC and ccl26 to assign a shared PCC once). "
        f"CAND_OFFICE_ST={state}, CAND_ELECTION_YR=2026, House+Senate only. "
        "MEMO_CD=X skipped. Joint committees (CMTE_DSGN=J) are not treated as PCC. "
        "Names are copied from the filing extract only and are never invented. "
        "Street addresses omitted. Donor lists are not sold. OpenFEC/DEMO_KEY is not used. "
        "No Ballotpedia. No scores."
    )
    return {
        "fec_api_key_present": False,
        "policy": policy,
        "by_candidate": by_candidate,
        "retrieved_at": RETRIEVED,
        "source_url": INDIV_URL,
        "sources": [
            {"url": INDIV_URL, "retrieved_at": RETRIEVED, "note": "FEC individual contributions bulk file (itcont.txt)."},
            {"url": CN_URL, "retrieved_at": RETRIEVED, "note": "FEC candidate master (CAND_PCC)."},
            {
                "url": CCL_URL,
                "retrieved_at": RETRIEVED,
                "note": "FEC candidate-committee linkage. Joint committees (CMTE_DSGN=J) are not treated as PCC. Shared CAND_PCC is assigned once via CMTE_DSGN=P.",
            },
            {"url": LAYOUT_URL, "retrieved_at": RETRIEVED, "note": "Individual contributions file layout."},
        ],
        "scope": STATE_SCOPE[state],
        "row_count": kept_unique,
        "candidate_count": len(by_candidate),
        "counts": {
            "candidates": len(by_candidate),
            "with_receipts": with_receipts,
            "honest_empty": empty,
            "kept_rows": kept_unique,
            "items_per_filer_cap": 25,
            "cycle": 2026,
            "election_year": 2026,
        },
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
    }


def merge_stub(state: str, payload: dict) -> None:
    stub_path = OUT / f"{state.lower()}.json"
    if not stub_path.exists():
        print(f"skip stub merge {stub_path} (missing)", flush=True)
        return
    stub = json.loads(stub_path.read_text(encoding="utf-8"))
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    block = {
        "status": "partial",
        "path": f"/data/{state.lower()}/fec-donors.json",
        "scope": STATE_SCOPE[state],
        "source_url": INDIV_URL,
        "retrieved_at": RETRIEVED,
        "counts": payload["counts"],
        "do_not_sell_donor_lists": True,
    }
    # Never wipe a sourced state donor extract; put FEC beside it.
    donors = (filings.get("donors") or {})
    if donors.get("status") == "sourced" or (donors.get("path") and "fec-donors" not in str(donors.get("path") or "")):
        filings["federal_fec"] = block
        if state == "FL" and donors.get("status") != "sourced":
            filings["donors"] = {
                "status": "pending",
                "reason": (
                    "Florida has no standing statewide campaign-finance bulk download URL; "
                    "Division of Elections campaign-finance access is form-limited. State donor "
                    "names are not invented. Federal FEC Schedule A $200+ is partial alongside."
                ),
                "do_not_sell_donor_lists": True,
            }
    else:
        filings["donors"] = block
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": INDIV_URL, "retrieved_at": RETRIEVED, "note": f"FEC bulk Schedule A $200+ ({state} federal only)"},
        {"url": CN_URL, "retrieved_at": RETRIEVED, "note": "FEC candidate master"},
        {"url": CCL_URL, "retrieved_at": RETRIEVED, "note": "FEC candidate-committee linkage"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    stub_path.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged {stub_path} fec candidates={payload['candidate_count']} kept={payload['row_count']}", flush=True)


def main() -> int:
    cn_path = pick_cn()
    ccl_path = pick_ccl()
    indiv_path = pick_indiv()
    by_state = parse_cn(cn_path)
    all_cands = [c for rows in by_state.values() for c in rows]
    owners = pcc_owners(ccl_path, {c["candidate_id"] for c in all_cands})
    claimed: dict[str, list[str]] = defaultdict(list)
    for rec in all_cands:
        if rec["committee_id"]:
            claimed[rec["committee_id"]].append(rec["candidate_id"])
    for pcc, ids in claimed.items():
        if pcc not in owners:
            owners[pcc] = min(ids)
    pccs = {c["committee_id"] for c in all_cands if c["committee_id"]}
    print(f"wave2 unique_pcc={len(pccs)} ccl_p_owners={len(owners)}", flush=True)
    by_cmte = scan_indiv(indiv_path, pccs)
    for state, cands in by_state.items():
        payload = build_payload(state, cands, owners, by_cmte)
        dest_dir = OUT / state.lower()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "fec-donors.json"
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        merge_stub(state, payload)
        print(f"wrote {dest} candidates={payload['candidate_count']} kept={payload['row_count']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
