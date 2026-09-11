#!/usr/bin/env python3
"""Rematch HI CSC CC11574 Souza, Kanani to site nominee SOUZA, Kanani.

Pages-only. Does not pull a new SODA extract. Official jexd-xbcg dump stays
18875 rows (Last-Modified Tue 01 Sep). Donor lists are not sold.

- CC11574 Souza, Kanani → matched_site_nominee SOUZA, Kanani (HD43), status ok, 9 items kept
- CC11581 Souza, Keoni (OHA) stays unmatched; do not attach to Kanani
- CC11978 Medeiros, Sheila stays matched and untouched
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
RETRIEVED = "2026-09-07T18:11:27Z"
REMATCHED = "2026-09-11T18:37:26Z"
SOURCE_URL = (
    "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
    "?$where=election_period%20like%20%27%252026%25%27"
)
LANDING = "https://ags.hawaii.gov/campaign/cc/view-searchable-data/"
CFS = "https://csc.hawaii.gov/CFSPublic/"
SITE = "SOUZA, Kanani"
KANANI = "CC11574"
KEONI = "CC11581"
MEDEIROS = "CC11978"
PACKAGE_DIRS = [
    Path("/workspace/wtp-live-data/donors-2026-09-11-souza-rematch"),
    Path("/tmp/wtp-live-data/donors-2026-09-11-souza-rematch"),
]
FEC_SHA256 = "0da3ef63f07e81cb9c1f67d685546e06b25c66d1dfd06794e2448e799abd8135"
VOTES_SHA256 = "0de4d06ca2f8af476efe8f2d16930e8fedf6f9b303f995dab0e78bb318d4369e"
CONGRESS_SHA256 = "e2082fcf811211cb404d700a270089a2153bea549f0f7017d3d6a7fc1a7a0e5b"
COUNTS = {
    "rows": 18875,
    "candidates": 249,
    "ok": 84,
    "unmatched": 163,
    "empty": 2,
    "election_periods": ["2022-2026", "2024-2026"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_never_wipe() -> None:
    if sha256(OUT / "donors.json") != FEC_SHA256:
        raise SystemExit("refusing to change FEC donors.json")
    if sha256(OUT / "hawaii-votes.json") != VOTES_SHA256:
        raise SystemExit("refusing to wipe hawaii-votes.json")
    if sha256(OUT / "congress-votes.json") != CONGRESS_SHA256:
        raise SystemExit("refusing to wipe congress-votes.json")


def load_packaged() -> dict | None:
    for d in PACKAGE_DIRS:
        primary = d / "ship-csc.json"
        if primary.is_file():
            data = json.loads(primary.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("by_candidate"):
                print(f"using packaged {primary}", flush=True)
                return data
        patch = d / "ship-csc-patch.json"
        if patch.is_file():
            print(f"using packaged patch {patch}", flush=True)
            base = json.loads((OUT / "csc-donors.json").read_text(encoding="utf-8"))
            overlay = json.loads(patch.read_text(encoding="utf-8"))
            if isinstance(overlay, dict) and overlay.get("by_candidate"):
                base.setdefault("by_candidate", {}).update(overlay["by_candidate"])
                return base
            if isinstance(overlay, dict) and overlay.get("reg_no"):
                base.setdefault("by_candidate", {})[overlay["reg_no"]] = overlay
                return base
    return None


def rematch_existing(payload: dict) -> dict:
    byc = payload.get("by_candidate") or {}
    kanani = byc.get(KANANI)
    keoni = byc.get(KEONI)
    medeiros = byc.get(MEDEIROS)
    if not kanani:
        raise SystemExit("CC11574 Souza, Kanani missing from CSC extract; refusing to invent receipts")
    if (kanani.get("official_name") or "") != "Souza, Kanani":
        raise SystemExit(f"CC11574 official_name unexpected: {kanani.get('official_name')}")
    if kanani.get("item_count_all") != 9 or len(kanani.get("items") or []) != 9:
        raise SystemExit("refusing to change CC11574 item count; 9 official items must be preserved")
    if not keoni or (keoni.get("official_name") or "") != "Souza, Keoni":
        raise SystemExit("CC11581 Souza, Keoni missing or renamed; refusing")
    if keoni.get("office") != ["OHA"]:
        raise SystemExit("CC11581 must stay OHA")
    if keoni.get("status") == "ok" or keoni.get("matched_site_nominee"):
        raise SystemExit("refusing to match OHA CC11581 Keoni")
    if not medeiros or medeiros.get("matched_site_nominee") != "MEDEIROS, Sheila":
        raise SystemExit("refusing to disturb Medeiros CC11978")
    if medeiros.get("status") != "ok" or medeiros.get("item_count_all") != 22:
        raise SystemExit("Medeiros CC11978 must stay ok with 22 items")

    medeiros_before = copy.deepcopy(medeiros)
    keoni_before = copy.deepcopy(keoni)
    items_before = copy.deepcopy(kanani.get("items") or [])

    kanani["status"] = "ok"
    kanani["matched_site_nominee"] = SITE
    kanani["reason"] = None
    kanani["retrieved_at"] = REMATCHED
    if kanani.get("items") != items_before:
        raise SystemExit("refusing to invent or rewrite CC11574 receipts")

    unmatched = [
        u
        for u in (payload.get("unmatched_official_names") or [])
        if not ((u.get("reg_no") == KANANI) or (u.get("official_name") == "Souza, Kanani"))
    ]
    if any((u.get("reg_no") == KEONI) or (u.get("official_name") == "Souza, Keoni") for u in unmatched) is False:
        unmatched.append(
            {
                "official_name": "Souza, Keoni",
                "reg_no": KEONI,
                "office": "OHA",
                "item_count_all": keoni.get("item_count_all") or 5,
            }
        )
    unmatched.sort(key=lambda r: (r.get("official_name") or "", r.get("reg_no") or ""))

    ok = sum(1 for v in byc.values() if v.get("status") == "ok")
    empty = sum(1 for v in byc.values() if (v.get("item_count_all") or 0) == 0)
    counts = dict(payload.get("counts") or {})
    counts.update(
        {
            "rows": 18875,
            "candidates": len(byc),
            "ok": ok,
            "unmatched": len(unmatched),
            "empty": empty,
            "election_periods": counts.get("election_periods") or COUNTS["election_periods"],
        }
    )
    payload["by_candidate"] = byc
    payload["unmatched_official_names"] = unmatched
    payload["counts"] = counts
    payload["candidate_count"] = len(byc)
    payload["row_count"] = 18875
    payload["retrieved_at"] = RETRIEVED
    payload["source_url"] = payload.get("source_url") or SOURCE_URL
    payload["do_not_sell_donor_lists"] = True
    payload["streets_omitted"] = True

    if byc[MEDEIROS] != medeiros_before:
        raise SystemExit("Medeiros CC11978 changed; abort")
    if byc[KEONI] != keoni_before:
        raise SystemExit("Keoni CC11581 changed; abort")
    if byc[KANANI].get("items") != items_before:
        raise SystemExit("Kanani items rewritten; abort")
    if counts["ok"] != 84 or counts["unmatched"] != 163 or empty != 2 or len(byc) != 249:
        raise SystemExit(f"expected CSC 249/ok 84/unmatched 163/empty 2, got {counts}")
    return payload


def validate(payload: dict) -> None:
    if payload.get("row_count") != 18875:
        raise SystemExit(f"CSC row_count {payload.get('row_count')} != 18875")
    if payload.get("retrieved_at") != RETRIEVED:
        raise SystemExit("refusing to change CSC retrieved_at / SODA dump timestamp")
    if not payload.get("do_not_sell_donor_lists") or not payload.get("streets_omitted"):
        raise SystemExit("CSC extract must omit streets and say do_not_sell_donor_lists")
    byc = payload.get("by_candidate") or {}
    kanani = byc.get(KANANI) or {}
    keoni = byc.get(KEONI) or {}
    medeiros = byc.get(MEDEIROS) or {}
    if kanani.get("matched_site_nominee") != SITE or kanani.get("status") != "ok":
        raise SystemExit("CC11574 must match SOUZA, Kanani with status ok")
    if kanani.get("item_count_all") != 9 or len(kanani.get("items") or []) != 9:
        raise SystemExit("CC11574 must keep 9 official items")
    if keoni.get("matched_site_nominee") in {SITE, "SOUZA, Keoni"} or keoni.get("status") == "ok":
        raise SystemExit("CC11581 Keoni/OHA must stay unmatched")
    if (keoni.get("official_name") or "") != "Souza, Keoni":
        raise SystemExit("CC11581 official name must stay Souza, Keoni")
    if medeiros.get("matched_site_nominee") != "MEDEIROS, Sheila" or medeiros.get("status") != "ok":
        raise SystemExit("CC11978 Medeiros must stay untouched")
    if any((u.get("official_name") == "Souza, Kanani") for u in payload.get("unmatched_official_names") or []):
        raise SystemExit("Souza, Kanani must leave unmatched_official_names")


def merge_hawaii() -> None:
    hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
    hd43 = (hi.get("nominees") or {}).get("State Representative, Dist 43") or []
    names = {n.get("name") for n in hd43}
    if names != {"MEDEIROS, Sheila", "SOUZA, Kanani"}:
        raise SystemExit(f"hawaii.json Dist 43 must stay Medeiros + Kanani Souza, got {names}")
    if any("Keoni" in (n.get("name") or "") for n in hd43):
        raise SystemExit("refusing to put OHA Keoni on Dist 43")
    donors = ((hi.get("state_filings") or {}).get("donors") or {})
    donors["status"] = "sourced"
    donors["path"] = "/data/csc-donors.json"
    donors["source_url"] = SOURCE_URL
    donors["retrieved_at"] = RETRIEVED
    donors["cfs_public"] = CFS
    donors["csc_searchable"] = LANDING
    donors["do_not_sell_donor_lists"] = True
    counts = dict(donors.get("counts") or {})
    counts.update({k: COUNTS[k] for k in ("rows", "candidates", "ok", "unmatched", "empty")})
    if "election_periods" in (donors.get("counts") or {}):
        counts["election_periods"] = donors["counts"]["election_periods"]
    donors["counts"] = counts
    hi.setdefault("state_filings", {})["donors"] = donors
    (OUT / "hawaii.json").write_text(json.dumps(hi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_meta() -> None:
    meta_path = OUT / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    extracts = meta.setdefault("donor_extracts", {})
    extracts["hawaii_csc"] = {
        "path": "/data/csc-donors.json",
        "retrieved_at": RETRIEVED,
        "source_url": SOURCE_URL,
        "counts": {k: COUNTS[k] for k in ("rows", "candidates", "ok", "unmatched", "empty")},
    }
    fed = extracts.get("federal") or {}
    if fed.get("retrieved_at") != "2026-08-31T14:40:58Z":
        raise SystemExit("refusing to change FEC donor_extracts retrieved_at")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    assert_never_wipe()
    packaged = load_packaged()
    if packaged:
        payload = rematch_existing(packaged)
    else:
        print("Origin package not mounted; applying rematch facts to committed csc-donors.json", flush=True)
        payload = rematch_existing(json.loads((OUT / "csc-donors.json").read_text(encoding="utf-8")))
    validate(payload)
    (OUT / "csc-donors.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    merge_hawaii()
    merge_meta()
    assert_never_wipe()
    print(
        json.dumps(
            {
                "csc_rows": 18875,
                "csc_ok": 84,
                "csc_unmatched": 163,
                "kanani": {"reg_no": KANANI, "matched_site_nominee": SITE, "status": "ok", "items": 9},
                "keoni": {"reg_no": KEONI, "status": "unmatched", "office": "OHA"},
                "medeiros": {"reg_no": MEDEIROS, "matched_site_nominee": "MEDEIROS, Sheila", "untouched": True},
                "retrieved_at": RETRIEVED,
                "soda_unchanged": True,
                "do_not_sell_donor_lists": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
