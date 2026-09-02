#!/usr/bin/env python3
"""Oregon federal FEC Schedule A $200+ extract from official indiv26 + cn26 (+ ccl26)."""

from __future__ import annotations

import json
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T12:14:47Z"
INDIV_URL = "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip"
CN_URL = "https://www.fec.gov/files/bulk-downloads/2026/cn26.zip"
CCL_URL = "https://www.fec.gov/files/bulk-downloads/2026/ccl26.zip"
LAYOUT_URL = "https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "or"
STUB = ROOT / "public" / "data" / "or.json"
CACHE = Path("/tmp/fec")
FRESH = Path("/tmp/fec-fresh")

POLICY = (
    "Official FEC bulk Schedule A individual receipts of $200+ from indiv26.zip "
    "(plus cn26 for CAND_PCC and ccl26 to assign a shared PCC once). "
    "CAND_OFFICE_ST=OR, CAND_ELECTION_YR=2026, House+Senate only. "
    "MEMO_CD=X skipped. Joint committees (CMTE_DSGN=J) are not treated as PCC. "
    "This is federal FEC only; Oregon has no free statewide ORESTAR/Schedule A bulk. "
    "Names are copied from the filing extract only and are never invented. "
    "Street addresses omitted. Donor lists are not sold. OpenFEC/DEMO_KEY is not used. "
    "No Ballotpedia. No scores."
)


def fetch_zip(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 200:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/zip,*/*;q=0.8"})
    with urlopen(req, timeout=600) as resp:
        dest.write_bytes(resp.read())
    return dest


def pick_cn() -> Path:
    fresh = FRESH / "cn26.zip"
    if fresh.exists() and fresh.stat().st_size > 200:
        return fresh
    return fetch_zip(CN_URL, CACHE / "cn26.zip")


def pick_ccl() -> Path:
    fresh = FRESH / "ccl26.zip"
    if fresh.exists() and fresh.stat().st_size > 200:
        return fresh
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


def parse_cn(path: Path) -> list[dict]:
    rows = []
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
        if rec["office_state"] != "OR" or rec["election_year"] != "2026":
            continue
        if rec["office"] not in {"H", "S"}:
            continue
        if not rec["candidate_id"] or not rec["candidate_name"]:
            raise SystemExit(f"cn26 missing official OR id/name: {rec}")
        rows.append(rec)
    if len(rows) != 40:
        raise SystemExit(f"expected 40 OR 2026 House+Senate cn26 rows, got {len(rows)}")
    return rows


def pcc_owners(path: Path, cand_ids: set[str]) -> dict[str, str]:
    """Map CMTE_ID -> CAND_ID for 2026 P-designated linkages of scoped candidates."""
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
            raise SystemExit(f"ccl26 P linkage conflict for {cmte}: {prev} vs {cand}")
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
    banned = {"street", "address", "addr", "zip", "zipcode", "contributor_zip", "occupation"}
    if banned & {k.lower() for k in item}:
        raise SystemExit("street/zip field leaked")
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


def build_payload(cands: list[dict], owners: dict[str, str], by_cmte: dict[str, list[dict]]) -> dict:
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
            "candidate_name": rec["candidate_name"],
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
    if len(by_candidate) != 40 or with_receipts != 25 or empty != 15 or kept_unique != 7522:
        raise SystemExit(
            f"expected 40/25/15/7522, got cands={len(by_candidate)} "
            f"with={with_receipts} empty={empty} kept={kept_unique}"
        )
    return {
        "fec_api_key_present": False,
        "policy": POLICY,
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
        "scope": (
            "Oregon 2026 House/Senate federal FEC Schedule A $200+ only. "
            "State ORESTAR donor bulk is not available for this populate."
        ),
        "row_count": kept_unique,
        "candidate_count": 40,
        "counts": {
            "candidates": 40,
            "with_receipts": 25,
            "honest_empty": 15,
            "kept_rows": 7522,
            "items_per_filer_cap": 25,
            "cycle": 2026,
            "election_year": 2026,
        },
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
    }


def merge_stub(payload: dict) -> None:
    stub = json.loads(STUB.read_text(encoding="utf-8"))
    cand_path = stub.get("candidates_path")
    votes_path = stub.get("votes_path")
    if cand_path != "/data/or/candidates.json" or votes_path != "/data/or/votes.json":
        raise SystemExit("refusing to merge: candidates_path/votes_path missing; do not wipe ballots/votes")
    election = stub.setdefault("election", {})
    election["jurisdiction"] = "Oregon"
    election["state_code"] = "OR"
    election["note"] = (
        "Official ORESTAR 2026 primary/general candidate filings, Clerk/LIS federal votes, "
        "and federal FEC Schedule A $200+ donors. State ORESTAR donor bulk is still blocked "
        "(no free statewide Schedule A dump). Donor lists are not sold."
    )
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    filings["orestar_public"] = filings.get("orestar_public") or "https://secure.sos.state.or.us/orestar/CFSearchPage.do"
    filings["donors"] = {
        "status": "partial",
        "path": "/data/or/fec-donors.json",
        "scope": (
            "Federal FEC Schedule A $200+ only (indiv26 + cn26 CAND_PCC). "
            "State ORESTAR Schedule A remains blocked; no free statewide bulk."
        ),
        "source_url": INDIV_URL,
        "retrieved_at": RETRIEVED,
        "counts": payload["counts"],
        "do_not_sell_donor_lists": True,
    }
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": INDIV_URL, "retrieved_at": RETRIEVED, "note": "FEC bulk Schedule A $200+ (OR federal only)"},
        {"url": CN_URL, "retrieved_at": RETRIEVED, "note": "FEC candidate master"},
        {"url": CCL_URL, "retrieved_at": RETRIEVED, "note": "FEC candidate-committee linkage"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    stub["candidates_path"] = "/data/or/candidates.json"
    stub["votes_path"] = "/data/or/votes.json"
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"merged {STUB} donors.status=partial candidates_path={stub['candidates_path']} votes_path={stub['votes_path']}",
        flush=True,
    )


def main() -> int:
    cn_path = pick_cn()
    ccl_path = pick_ccl()
    indiv_path = pick_indiv()
    cands = parse_cn(cn_path)
    owners = pcc_owners(ccl_path, {c["candidate_id"] for c in cands})
    pccs = {c["committee_id"] for c in cands if c["committee_id"]}
    print(f"OR 2026 H+S={len(cands)} unique_pcc={len(pccs)} ccl_p_owners={len(owners)}", flush=True)
    by_cmte = scan_indiv(indiv_path, pccs)
    payload = build_payload(cands, owners, by_cmte)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "fec-donors.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    merge_stub(payload)
    print(
        f"wrote {dest} candidates={payload['candidate_count']} kept={payload['row_count']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
