#!/usr/bin/env python3
"""Add HANNA, Max G. as CSC honest-empty (same pattern as Kitashima).

Official SODA jexd-xbcg election_period-contains-2026 is still 18875 rows and has
no Schedule A for HANNA, Max G. Do not attach Test, Hannah (CC12084).
FEC donors.json is not rewritten. Donor lists are not sold.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
RETRIEVED = "2026-09-07T18:11:27Z"
SOURCE_URL = (
    "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
    "?$where=election_period%20like%20%27%252026%25%27"
)
LANDING = "https://ags.hawaii.gov/campaign/cc/view-searchable-data/"
CFS = "https://csc.hawaii.gov/CFSPublic/"
NAME = "HANNA, Max G."
KEY = NAME
KIT = "KITASHIMA, Kelly Puamailani"
FEC_SHA256 = "0da3ef63f07e81cb9c1f67d685546e06b25c66d1dfd06794e2448e799abd8135"
VOTES_SHA256 = "0de4d06ca2f8af476efe8f2d16930e8fedf6f9b303f995dab0e78bb318d4369e"
CONGRESS_SHA256 = "e2082fcf811211cb404d700a270089a2153bea549f0f7017d3d6a7fc1a7a0e5b"
PACKAGE_DIRS = [
    Path("/workspace/wtp-live-data/donors-2026-09-07"),
    Path("/tmp/wtp-live-data/donors-2026-09-07"),
]
REASON = (
    "Official Hawaii CSC SODA Schedule A (jexd-xbcg, election_period contains 2026) "
    "has 0 rows for this OLVR general nominee. Test candidate Hannah (CC12084) is a "
    "different name and is not copied. Receipts are not invented. Donor lists are not sold."
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_never_wipe() -> None:
    got = sha256(OUT / "donors.json")
    if got != FEC_SHA256:
        raise SystemExit(f"refusing to change FEC donors.json: {got}")
    fec = json.loads((OUT / "donors.json").read_text(encoding="utf-8"))
    if any("HANNA" in json.dumps(v).upper() for v in (fec.get("by_candidate") or {}).values()):
        raise SystemExit("refusing to invent Hanna as a federal FEC donor")
    if sha256(OUT / "hawaii-votes.json") != VOTES_SHA256:
        raise SystemExit("refusing to wipe hawaii-votes.json")
    if sha256(OUT / "congress-votes.json") != CONGRESS_SHA256:
        raise SystemExit("refusing to wipe congress-votes.json")


def hanna_row() -> dict:
    return {
        "official_name": NAME,
        "reg_no": None,
        "office": ["State Senator, Dist 18 Vacancy"],
        "election_periods": [],
        "status": "empty",
        "matched_site_nominee": NAME,
        "reason": REASON,
        "item_count_all": 0,
        "items": [],
        "retrieved_at": RETRIEVED,
        "source_url": SOURCE_URL,
        "do_not_sell_donor_lists": True,
    }


def load_packaged() -> dict | None:
    for d in PACKAGE_DIRS:
        for name in ("ship-csc.json", "csc-schedule-a.json", "csc-donors.json"):
            p = d / name
            if not p.is_file():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("by_candidate"):
                print(f"using packaged {p}", flush=True)
                return data
    return None


def apply_csc(payload: dict) -> dict:
    if payload.get("row_count") != 18875:
        raise SystemExit(f"CSC row_count {payload.get('row_count')} != 18875")
    byc = dict(payload.get("by_candidate") or {})
    for k, v in byc.items():
        official = (v.get("official_name") or "").strip().upper()
        if (v.get("reg_no") or k) == "CC12084" and official in {
            NAME.upper(),
            "HANNA, MAX G",
            "MAX G. HANNA",
            "MAX HANNA",
        }:
            raise SystemExit("refusing to attach Test Hannah CC12084 to Max Hanna")
    kit = next((v for v in byc.values() if v.get("matched_site_nominee") == KIT), None)
    if not kit or kit.get("status") != "empty" or kit.get("item_count_all") != 0:
        raise SystemExit("Kitashima CSC empty row missing; refusing")
    byc = {k: v for k, v in byc.items() if (v.get("matched_site_nominee") or v.get("official_name")) != NAME}
    byc[KEY] = hanna_row()
    byc = dict(sorted(byc.items(), key=lambda kv: (kv[1].get("official_name") or "", kv[0])))
    empty = sum(1 for v in byc.values() if (v.get("item_count_all") or 0) == 0)
    ok = sum(1 for v in byc.values() if v.get("status") == "ok")
    unmatched = payload.get("unmatched_official_names") or []
    counts = dict(payload.get("counts") or {})
    counts.update({"rows": 18875, "candidates": len(byc), "ok": ok, "unmatched": len(unmatched), "empty": empty})
    payload["by_candidate"] = byc
    payload["candidate_count"] = len(byc)
    payload["counts"] = counts
    payload["row_count"] = 18875
    payload["retrieved_at"] = RETRIEVED
    payload["source_url"] = payload.get("source_url") or SOURCE_URL
    payload["do_not_sell_donor_lists"] = True
    payload["streets_omitted"] = True
    if empty != 2 or len(byc) != 249:
        raise SystemExit(f"expected CSC 249/empty 2 after Hanna, got {len(byc)}/{empty}")
    return payload


def merge_hawaii() -> None:
    hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
    sd = (hi.get("nominees") or {}).get("State Senator, Dist 18 Vacancy") or []
    hanna = next((n for n in sd if n.get("name") == NAME), None)
    if not hanna:
        raise SystemExit("hawaii.json missing OLVR Hanna; refusing to invent a nominee")
    if hanna.get("status") != "In General" or hanna.get("party_code") != "N":
        raise SystemExit("Hanna must stay official OLVR Nonpartisan In General")
    hanna["donors"] = {
        "status": "empty",
        "item_count_all": 0,
        "source": "csc",
        "reason": REASON,
        "source_url": SOURCE_URL,
        "retrieved_at": RETRIEVED,
        "do_not_sell_donor_lists": True,
    }
    donors = ((hi.get("state_filings") or {}).get("donors") or {})
    donors["status"] = "sourced"
    donors["path"] = "/data/csc-donors.json"
    donors["source_url"] = SOURCE_URL
    donors["retrieved_at"] = RETRIEVED
    donors["cfs_public"] = CFS
    donors["csc_searchable"] = LANDING
    donors["do_not_sell_donor_lists"] = True
    counts = dict(donors.get("counts") or {})
    counts.update({"rows": 18875, "candidates": 249, "ok": 83, "unmatched": 164, "empty": 2})
    donors["counts"] = counts
    hi.setdefault("state_filings", {})["donors"] = donors
    (OUT / "hawaii.json").write_text(json.dumps(hi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_meta() -> None:
    meta_path = OUT / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    for src in meta.get("sources") or []:
        if "jexd-xbcg" in (src.get("url") or ""):
            src["retrieved_at"] = RETRIEVED
    extracts = meta.setdefault("donor_extracts", {})
    extracts["hawaii_csc"] = {
        "path": "/data/csc-donors.json",
        "retrieved_at": RETRIEVED,
        "source_url": SOURCE_URL,
        "counts": {"rows": 18875, "candidates": 249, "ok": 83, "unmatched": 164, "empty": 2},
    }
    fed = extracts.get("federal") or {}
    if fed.get("path") != "/data/donors.json":
        raise SystemExit("federal donors path missing")
    if fed.get("retrieved_at") != "2026-08-31T14:40:58Z":
        raise SystemExit("refusing to change FEC donor_extracts retrieved_at")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    assert_never_wipe()
    packaged = load_packaged()
    if packaged:
        payload = apply_csc(packaged)
    else:
        print("Origin package not mounted; applying official SODA-confirmed Hanna empty row", flush=True)
        payload = apply_csc(json.loads((OUT / "csc-donors.json").read_text(encoding="utf-8")))
    (OUT / "csc-donors.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    merge_hawaii()
    merge_meta()
    assert_never_wipe()
    print(
        json.dumps(
            {
                "csc_rows": 18875,
                "csc_candidates": 249,
                "csc_empty": 2,
                "hanna": "empty",
                "kitashima": "empty",
                "retrieved_at": RETRIEVED,
                "fec_unchanged": True,
                "hanna_in_fec_donors_json": False,
                "do_not_sell_donor_lists": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
