#!/usr/bin/env python3
"""USVI federal FEC Schedule A $200+ (9 as-filed H/S, 4 with receipts, 326 kept).

Does not overwrite /data/vi/candidates.json or invent votes. Territorial CF stays pending.
The one Senate as-filed row is honest-empty and is not a VI Senate contest.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-03T13:54:09Z"
INDIV_URL = "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip"
CN_URL = "https://www.fec.gov/files/bulk-downloads/2026/cn26.zip"
CCL_URL = "https://www.fec.gov/files/bulk-downloads/2026/ccl26.zip"
LAYOUT_URL = "https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "vi"
STUB = ROOT / "public" / "data" / "vi.json"
CANDS = OUT_DIR / "candidates.json"
CACHE = Path("/tmp/fec")
FRESH = Path("/tmp/fec-fresh")
PACKAGE = Path("/workspace/wtp-live-data/donors-50state/2026-09-03/vi")
EXPECT_CANDS = 9
EXPECT_WITH = 4
EXPECT_EMPTY = 5
EXPECT_KEPT = 326
SENATE_ID = "S6VI00018"
PRESERVE = {
    "public/data/vi/candidates.json": "dc286c85135f544b16a7a93022d18514952b0128",
    "public/data/vi/candidate-summary.json": "29df60ad40b36a7f0a96961e22da7aeae249962c",
    "public/data/csc-donors.json": "e3f50aec5328a5eb91ce31b99074b9ec993d8285",
    "public/data/hawaii.json": "f8872a11576f4bd6b69913853f6e69f2745e84f8",
    "public/data/congress-votes.json": "e0956a887dafd376680094bf67ba7ab46eebf89a",
    "public/data/donors.json": "f9e15cc1bb7f67757da6f52ccab38c2afc58826d",
}

POLICY = (
    "Official FEC bulk Schedule A individual receipts of $200+ from indiv26.zip "
    "(plus cn26 for CAND_PCC and ccl26 to assign a shared PCC once). "
    "CAND_OFFICE_ST=VI, CAND_ELECTION_YR=2026, House+Senate as-filed only. "
    "MEMO_CD=X skipped. Joint committees (CMTE_DSGN=J) are not treated as PCC. "
    "The U.S. Virgin Islands has no U.S. Senate seat; the one Senate as-filed row "
    "is kept honest-empty and is not a VI Senate contest. "
    "This is federal FEC only; territorial campaign-finance bulk is pending. "
    "Names are copied from the filing extract only and are never invented. "
    "Street addresses omitted. Donor lists are not sold. OpenFEC/DEMO_KEY is not used. "
    "No Ballotpedia. No scores."
)


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def assert_preserved() -> None:
    for rel, digest in PRESERVE.items():
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"refusing to wipe missing {rel}")
        got = sha1(p)
        if got != digest:
            raise SystemExit(f"refusing to wipe {rel}: {digest} -> {got}")


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
        if rec["office_state"] != "VI" or rec["election_year"] != "2026":
            continue
        if rec["office"] not in {"H", "S"}:
            continue
        if not rec["candidate_id"] or not rec["candidate_name"]:
            raise SystemExit(f"cn26 missing official VI id/name: {rec}")
        rows.append(rec)
    if len(rows) != EXPECT_CANDS:
        raise SystemExit(f"expected {EXPECT_CANDS} VI 2026 House+Senate cn26 rows, got {len(rows)}")
    if not any(r["candidate_id"] == SENATE_ID and r["office"] == "S" for r in rows):
        raise SystemExit("expected as-filed Senate row S6VI00018")
    return rows


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


def senate_empty_reason(pcc: str | None) -> str:
    return (
        "As-filed FEC Senate registration (S6VI00018). The U.S. Virgin Islands has no "
        "U.S. Senate seat. This row is kept as an honest-empty as-filed filing and is "
        "not a VI Senate contest."
        + (f" Principal campaign committee {pcc} has no Schedule A $200+ receipts." if pcc else "")
    )


def build_payload(cands: list[dict], owners: dict[str, str], by_cmte: dict[str, list[dict]]) -> dict:
    by_candidate: dict[str, dict] = {}
    kept_unique = 0
    with_receipts = 0
    for rec in sorted(cands, key=lambda r: r["candidate_id"]):
        pcc = rec["committee_id"]
        owner = owners.get(pcc) if pcc else None
        if rec["candidate_id"] == SENATE_ID:
            items_all: list[dict] = []
            status = "empty"
            reason = senate_empty_reason(pcc)
            committee_id = pcc
        elif pcc and owner and owner != rec["candidate_id"]:
            items_all = []
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
        if rec["candidate_id"] == SENATE_ID:
            by_candidate[rec["candidate_id"]]["not_a_contest"] = True
            by_candidate[rec["candidate_id"]]["no_us_senate_seat"] = True
    empty = sum(1 for v in by_candidate.values() if v["status"] == "empty")
    senate = by_candidate.get(SENATE_ID) or {}
    if senate.get("item_count_all") or senate.get("items"):
        raise SystemExit("Senate as-filed row must stay honest-empty")
    if (
        len(by_candidate) != EXPECT_CANDS
        or with_receipts != EXPECT_WITH
        or empty != EXPECT_EMPTY
        or kept_unique != EXPECT_KEPT
    ):
        raise SystemExit(
            f"expected {EXPECT_CANDS}/{EXPECT_WITH}/{EXPECT_EMPTY}/{EXPECT_KEPT}, "
            f"got cands={len(by_candidate)} with={with_receipts} empty={empty} kept={kept_unique}"
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
            "U.S. Virgin Islands 2026 Delegate federal FEC Schedule A $200+ only. "
            "No U.S. Senate seat; one Senate as-filed row is honest-empty and is not a contest. "
            "Territorial campaign-finance bulk is pending."
        ),
        "row_count": kept_unique,
        "candidate_count": EXPECT_CANDS,
        "counts": {
            "candidates": EXPECT_CANDS,
            "with_receipts": EXPECT_WITH,
            "honest_empty": EXPECT_EMPTY,
            "kept_rows": EXPECT_KEPT,
            "items_per_filer_cap": 25,
            "cycle": 2026,
            "election_year": 2026,
            "senate_as_filed_empty": 1,
        },
        "no_us_senate": True,
        "no_us_senate_contest": True,
        "do_not_sell_donor_lists": True,
        "streets_omitted": True,
    }


def from_package() -> dict | None:
    if not PACKAGE.is_dir():
        return None
    for name in ("vi-fec-schedule-a.json", "fec-donors.json", "ship-donors.json"):
        dest = PACKAGE / name
        if dest.exists():
            payload = json.loads(dest.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("row_count") == EXPECT_KEPT:
                return payload
    return None


def merge_stub(payload: dict) -> None:
    if not STUB.exists():
        raise SystemExit("refusing to merge: vi.json missing")
    stub = json.loads(STUB.read_text(encoding="utf-8"))
    if stub.get("candidates_path") != "/data/vi/candidates.json":
        raise SystemExit("refusing to merge: candidates_path missing; do not wipe ballots")
    if stub.get("votes_path"):
        raise SystemExit("refusing to invent or overwrite votes_path")
    if not CANDS.exists() or len(json.loads(CANDS.read_text(encoding="utf-8"))) != 166:
        raise SystemExit("refusing to merge: candidates.json is not the 166-row ESVI extract")
    election = stub.setdefault("election", {})
    election["jurisdiction"] = "U.S. Virgin Islands"
    election["state_code"] = "VI"
    election["prefer_for_november"] = "official_august"
    election["no_us_senate"] = True
    election["federal_offices"] = ["Delegate to Congress"]
    election["note"] = (
        "Official Election System of the Virgin Islands June certification (88 rows) plus "
        "August general listing (70 rows) and FEC 2026 Delegate master (8 rows). "
        "Federal FEC Schedule A $200+ is partial (9 as-filed H/S rows, 4 with receipts, "
        "326 kept). Prefer August general for November. No U.S. Senate; Delegate is the "
        "only federal office. Territorial campaign-finance bulk is pending. Streets omitted. "
        "Donor lists are not sold."
    )
    filings = stub.setdefault("state_filings", {})
    filings["wired"] = True
    candidates_block = filings.get("candidates")
    if not candidates_block or candidates_block.get("path") != "/data/vi/candidates.json":
        raise SystemExit("refusing to wipe state_filings.candidates")
    filings["donors"] = {
        "status": "partial",
        "path": "/data/vi/fec-donors.json",
        "scope": (
            "U.S. Virgin Islands 2026 Delegate federal FEC Schedule A $200+ only "
            "(indiv26 + cn26 CAND_PCC). No U.S. Senate seat; one Senate as-filed row "
            "is honest-empty and is not a contest. Territorial campaign-finance bulk is pending."
        ),
        "source_url": INDIV_URL,
        "retrieved_at": RETRIEVED,
        "counts": payload["counts"],
        "no_us_senate": True,
        "do_not_sell_donor_lists": True,
    }
    filings["state_donors"] = {
        "status": "pending",
        "reason": (
            "Virgin Islands territorial campaign-finance bulk is not extracted in this populate. "
            "Territorial donor names are not invented. Federal FEC Schedule A $200+ is partial."
        ),
        "do_not_sell_donor_lists": True,
    }
    filings["candidates"] = candidates_block
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": INDIV_URL, "retrieved_at": RETRIEVED, "note": "FEC bulk Schedule A $200+ (VI federal only)"},
        {"url": CN_URL, "retrieved_at": RETRIEVED, "note": "FEC candidate master"},
        {"url": CCL_URL, "retrieved_at": RETRIEVED, "note": "FEC candidate-committee linkage"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
        else:
            for existing in sources:
                if existing.get("url") == src["url"] and "cn26" in src["url"]:
                    existing.setdefault("note", src["note"])
    stub["candidates_path"] = "/data/vi/candidates.json"
    stub["candidate_summary_path"] = "/data/vi/candidate-summary.json"
    stub.pop("votes_path", None)
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"merged {STUB} donors.status=partial candidates_path={stub['candidates_path']} no votes_path",
        flush=True,
    )


def main() -> int:
    assert_preserved()
    payload = from_package()
    if payload is None:
        cn_path = pick_cn()
        ccl_path = pick_ccl()
        indiv_path = pick_indiv()
        cands = parse_cn(cn_path)
        owners = pcc_owners(ccl_path, {c["candidate_id"] for c in cands})
        pccs = {c["committee_id"] for c in cands if c["committee_id"]}
        print(f"VI 2026 H+S={len(cands)} unique_pcc={len(pccs)} ccl_p_owners={len(owners)}", flush=True)
        by_cmte = scan_indiv(indiv_path, pccs)
        payload = build_payload(cands, owners, by_cmte)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "fec-donors.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    merge_stub(payload)
    assert_preserved()
    print(
        f"wrote {dest} candidates={payload['candidate_count']} kept={payload['row_count']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
