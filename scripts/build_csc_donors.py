#!/usr/bin/env python3
"""Refresh Hawaii CSC Schedule A from official SODA (or a cached package).

Does not rewrite FEC donors.json. Streets omitted. Donor lists are not sold.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
RETRIEVED = "2026-09-02T18:11:34Z"
SOURCE_URL = (
    "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
    "?$where=election_period%20like%20%27%252026%25%27"
)
LANDING = "https://ags.hawaii.gov/campaign/cc/view-searchable-data/"
CFS = "https://csc.hawaii.gov/CFSPublic/"
POLICY = (
    "Official Hawaii Campaign Spending Commission Schedule A extract via the public "
    "SODA resource jexd-xbcg (election_period contains 2026). Street addresses are omitted. "
    "Names are copied from the official file only and are never invented. Donor lists are not sold. "
    "Site nominee matches are not forced; unmatched official names are kept and flagged."
)
UNMATCHED_REASON = (
    "Official CSC name was not matched to a site nominee; kept and flagged. Matches are not forced."
)
# Official CSC legal-style name → OE ballot name when first-token match is not enough.
# First-run extract matched La Chica this way; first names (Mae Patricia vs Trish) do not overlap.
ALIASES = {
    "LA CHICA, MAE PATRICIA": "LA CHICA, Trish",
}
PACKAGE_DIRS = [
    Path("/workspace/wtp-live-data/donors-2026-09-02"),
    Path("/workspace/wtp-live-data/run-2026-09-02-hi08-routine"),
    Path("/tmp/hi-official"),
]
STREET_KEYS = {
    "street",
    "address",
    "addr",
    "street_address_1",
    "street_address_2",
    "contributor_street_1",
    "contributor_street_2",
    "mapping_address",
    "zip_code",
    "zip",
}
ITEM_CAP = 25


def fetch_soda() -> list[dict]:
    for d in PACKAGE_DIRS:
        for name in ("csc-schedule-a.json", "ship-csc.json"):
            p = d / name
            if not p.exists():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list) and data and "contributor_name" in data[0]:
                print(f"Using cached SODA rows {p} ({len(data)})", flush=True)
                return data
            if isinstance(data, dict) and data.get("by_candidate"):
                print(f"Using packaged ship-csc {p}", flush=True)
                return data  # type: ignore[return-value]
    base = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
    where = "election_period like '%2026%'"
    rows: list[dict] = []
    limit = 1000
    offset = 0
    while True:
        q = urllib.parse.urlencode(
            {"$where": where, "$limit": limit, "$offset": offset, "$order": ":id"}
        )
        url = f"{base}?{q}"
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            chunk = json.loads(resp.read().decode("utf-8"))
        print(f"SODA offset {offset} got {len(chunk)}", flush=True)
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < limit:
            break
        offset += limit
        time.sleep(0.15)
    return rows


def fold_last(name: str) -> str:
    left = (name or "").split(",", 1)[0]
    left = re.sub(r"\*$", "", left).strip()
    return re.sub(r"\s+", " ", left).upper()


def first_tokens(name: str) -> list[str]:
    rest = (name or "").split(",", 1)[1] if "," in (name or "") else ""
    rest = re.sub(r"\*$", "", rest).strip()
    rest = re.sub(r"\([^)]*\)", " ", rest)
    skip = {"II", "III", "IV", "JR", "SR", "I"}
    toks = []
    for t in re.split(r"[^A-Za-z]+", rest):
        u = t.upper()
        if len(u) > 1 and u not in skip:
            toks.append(u)
    return toks


def match_nominee(official: str, nominees: list[dict]) -> str | None:
    key = re.sub(r"\s+", " ", re.sub(r"\*$", "", official or "")).strip().upper()
    alias = ALIASES.get(key)
    if alias:
        return alias
    last = fold_last(official)
    toks = first_tokens(official)
    if not last or not toks:
        return None
    hits = []
    for n in nominees:
        site = n.get("name") or ""
        if fold_last(site) != last:
            continue
        site_toks = first_tokens(site)
        if site_toks and toks[0] == site_toks[0]:
            hits.append(site)
    uniq = list(dict.fromkeys(hits))
    if len(uniq) == 1:
        return uniq[0]
    return None


def parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw[:10]


def parse_amount(raw) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    fec_path = OUT / "donors.json"
    fec_hash = sha256(fec_path)
    votes_hash = sha256(OUT / "hawaii-votes.json")

    raw = fetch_soda()
    if isinstance(raw, dict) and raw.get("by_candidate"):
        payload = raw
        if payload.get("row_count") != 18875:
            raise SystemExit(f"packaged CSC row_count {payload.get('row_count')} != 18875")
    else:
        if len(raw) != 18875:
            raise SystemExit(f"official SODA rows {len(raw)} != 18875")
        hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
        nominees = []
        for rows in (hi.get("nominees") or {}).values():
            nominees.extend(rows)

        grouped: dict[str, list[dict]] = defaultdict(list)
        for rec in raw:
            grouped[str(rec.get("reg_no") or "")].append(rec)

        by_candidate = {}
        unmatched = []
        ok = 0
        for reg_no, recs in grouped.items():
            names = [r.get("candidate_name") for r in recs if r.get("candidate_name")]
            official = names[0] if names else ""
            offices = sorted({r.get("office") for r in recs if r.get("office")})
            periods = sorted({r.get("election_period") for r in recs if r.get("election_period")})
            items_all = []
            for r in recs:
                item = {
                    "contributor_name": r.get("contributor_name"),
                    "amount": parse_amount(r.get("amount")),
                    "date": parse_date(r.get("date")),
                    "city": r.get("city"),
                    "state": r.get("state"),
                    "employer": r.get("employer"),
                    "occupation": r.get("occupation"),
                    "contributor_type": r.get("contributor_type"),
                    "election_period": r.get("election_period"),
                    "retrieved_at": RETRIEVED,
                    "source_url": SOURCE_URL,
                }
                if STREET_KEYS & {k.lower() for k in item}:
                    raise SystemExit("refusing to write street fields")
                items_all.append(item)
            items_all.sort(
                key=lambda it: (
                    -(it["amount"] if it["amount"] is not None else -1),
                    it.get("date") or "",
                    it.get("contributor_name") or "",
                )
            )
            matched = match_nominee(official, nominees)
            status = "ok" if matched else "unmatched"
            if matched:
                ok += 1
                reason = None
            else:
                unmatched.append(
                    {
                        "official_name": official,
                        "reg_no": reg_no,
                        "office": offices[0] if offices else None,
                        "item_count_all": len(items_all),
                    }
                )
                reason = UNMATCHED_REASON
            by_candidate[reg_no] = {
                "official_name": official,
                "reg_no": reg_no,
                "office": offices,
                "election_periods": periods,
                "status": status,
                "matched_site_nominee": matched,
                "reason": reason,
                "item_count_all": len(items_all),
                "items": items_all[:ITEM_CAP],
                "retrieved_at": RETRIEVED,
                "source_url": SOURCE_URL,
            }

        # Stable order: official name, then reg_no (matches first-run readability).
        by_candidate = dict(
            sorted(by_candidate.items(), key=lambda kv: (kv[1]["official_name"] or "", kv[0]))
        )
        unmatched.sort(key=lambda r: (r.get("official_name") or "", r.get("reg_no") or ""))
        empty = sum(1 for v in by_candidate.values() if v["item_count_all"] == 0)
        periods = sorted({p for recs in grouped.values() for r in recs if (p := r.get("election_period"))})
        payload = {
            "policy": POLICY,
            "by_candidate": by_candidate,
            "retrieved_at": RETRIEVED,
            "source_url": SOURCE_URL,
            "landing_url": LANDING,
            "cfs_public_url": CFS,
            "row_count": len(raw),
            "candidate_count": len(by_candidate),
            "counts": {
                "rows": len(raw),
                "candidates": len(by_candidate),
                "ok": ok,
                "unmatched": len(unmatched),
                "empty": empty,
                "election_periods": periods,
            },
            "unmatched_official_names": unmatched,
            "do_not_sell_donor_lists": True,
            "streets_omitted": True,
        }

    if not payload.get("do_not_sell_donor_lists") or not payload.get("streets_omitted"):
        raise SystemExit("CSC extract must omit streets and say do_not_sell_donor_lists")
    if payload.get("row_count") != 18875:
        raise SystemExit(f"row_count {payload.get('row_count')} != 18875")
    if payload.get("retrieved_at") != RETRIEVED:
        payload["retrieved_at"] = RETRIEVED

    # Refuse to write if FEC / votes / other live extracts vanished.
    required = [
        OUT / "donors.json",
        OUT / "hawaii-votes.json",
        OUT / "hawaii.json",
        OUT / "ny" / "nysboe-donors.json",
        OUT / "ny" / "fec-donors.json",
        OUT / "ny" / "votes.json",
        OUT / "il" / "sbe-donors.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"refusing to wipe; missing {missing}")

    (OUT / "csc-donors.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
    donors = (hi.get("state_filings") or {}).get("donors") or {}
    donors["status"] = "sourced"
    donors["path"] = "/data/csc-donors.json"
    donors["source_url"] = payload.get("source_url") or SOURCE_URL
    donors["retrieved_at"] = RETRIEVED
    donors["counts"] = payload.get("counts")
    donors["reason"] = payload.get("policy") or POLICY
    donors["cfs_public"] = CFS
    donors["csc_searchable"] = LANDING
    hi.setdefault("state_filings", {})["donors"] = donors
    (OUT / "hawaii.json").write_text(json.dumps(hi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
        "counts": payload.get("counts"),
    }
    # Reaffirm FEC extract metadata; do not rewrite donors.json.
    fed = extracts.get("federal") or {}
    if fed.get("retrieved_at") != "2026-08-31T14:40:58Z":
        raise SystemExit("refusing to change FEC donor_extracts retrieved_at")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if sha256(fec_path) != fec_hash:
        raise SystemExit("FEC donors.json changed; abort")
    if sha256(OUT / "hawaii-votes.json") != votes_hash:
        raise SystemExit("hawaii-votes.json changed; abort")

    print(
        json.dumps(
            {
                "csc_rows": payload.get("row_count"),
                "candidates": payload.get("candidate_count"),
                "counts": payload.get("counts"),
                "retrieved_at": payload.get("retrieved_at"),
                "fec_sha256_unchanged": True,
                "do_not_sell_donor_lists": True,
                "streets_omitted": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
