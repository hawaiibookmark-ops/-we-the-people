#!/usr/bin/env python3
"""Sanity-check gold-template ZIPs and committed donor extracts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "public" / "data"
zips = json.loads((ROOT / "zips.json").read_text())
hi = json.loads((ROOT / "hawaii.json").read_text())
fed = json.loads((ROOT / "federal.json").read_text())
donors = json.loads((ROOT / "donors.json").read_text())
csc = json.loads((ROOT / "csc-donors.json").read_text())

errors = []

r = zips.get("96813")
if not r or r.get("s") != "HI" or r["cd"][0][0] != "01":
    errors.append(f"96813 should be HI-01, got {r}")
if r and r.get("island") != "Oʻahu":
    errors.append(f"96813 island {r.get('island')}")
noms = hi["nominees"].get("U.S. Representative, Dist I") or []
names = {n["name"] for n in noms}
if "CASE, Ed" not in names or "LAM, Adriel C." not in names:
    errors.append(f"HI-01 OE nominees missing Case/Lam: {names}")
if "IWAMOTO, Kim Coco" not in {n["name"] for n in hi["nominees"].get("State Representative, Dist 25", [])}:
    errors.append("HD25 nominee missing Iwamoto")
if "NAKAMATSU, Tricia Kwai Lin" not in {n["name"] for n in hi["nominees"].get("State Senator, Dist 13", [])}:
    errors.append("SD13 nominee missing Nakamatsu")

r = zips.get("90210")
if not r or r.get("s") != "CA":
    errors.append(f"90210 should be CA, got {r}")
dists = {c[0] for c in r["cd"]} if r else set()
if not {"32", "36"} <= dists:
    errors.append(f"90210 should overlap CA-32 and CA-36, got {dists}")
if not fed.get("CA", {}).get("state_filings_note"):
    errors.append("CA should say state filings not wired yet")

r = zips.get("82001")
if not r or r.get("s") != "WY" or r["cd"][0][0] != "00":
    errors.append(f"82001 should be WY at-large, got {r}")
if not fed.get("WY", {}).get("senate_regular_2026"):
    errors.append("WY should have a 2026 Senate class II seat")

# Federal Schedule A bulk extract
if donors.get("fec_api_key_present"):
    errors.append("fec_api_key_present must be false (OpenFEC/DEMO_KEY is not used)")
src = donors.get("source_url") or ""
if "open.fec.gov" in src:
    errors.append("donors.json must not use OpenFEC / DEMO_KEY")
if "indiv26.zip" not in src:
    errors.append(f"donors.json source_url should be FEC bulk indiv26, got {src}")
if not donors.get("retrieved_at"):
    errors.append("donors.json missing retrieved_at")
if not donors.get("by_candidate"):
    errors.append("donors.json by_candidate is empty")
if not donors.get("do_not_sell_donor_lists"):
    errors.append("donors.json must say do_not_sell_donor_lists")
policy = donors.get("policy") or ""
if "OpenFEC" not in policy or "not sold" not in policy.lower():
    errors.append("donor policy must name official FEC bulk, no invented names, do not sell lists")

expected = {
    "H2HI02128": 430,
    "H2HI02581": 604,
    "H6HI01311": 795,
    "H6HI01345": 118,
    "H6HI02426": 74,
    "H6HI01337": 0,
    "H6HI01352": 0,
    "H6HI01360": 0,
    "H6HI01378": 0,
    "H6HI01386": 0,
    "S6HI00313": 0,
    "S6HI00321": 0,
}
for cid, n in expected.items():
    row = (donors.get("by_candidate") or {}).get(cid) or {}
    got = row.get("item_count_all")
    if got != n:
        errors.append(f"{cid} item_count_all {got} != this extract {n}")
    items = row.get("items") or []
    if n > 0:
        if len(items) != min(25, n):
            errors.append(f"{cid} expected top {min(25, n)} items, got {len(items)}")
        for it in items:
            if not it.get("contributor_name"):
                errors.append(f"{cid} item missing contributor_name")
            if not it.get("fec_url"):
                errors.append(f"{cid} item missing fec_url")
            if it.get("amount") is None:
                errors.append(f"{cid} item missing amount")
    else:
        if items:
            errors.append(f"{cid} honest-empty should have no items")

gelt = (donors.get("by_candidate") or {}).get("H6HI01378") or {}
if gelt.get("committee_id"):
    errors.append("Gelt must have no PCC")
sol = (donors.get("by_candidate") or {}).get("S6HI00321") or {}
if sol.get("committee_id"):
    errors.append("Solomon must have no PCC (do not use joint C00915710)")
if sol.get("committee_id") == "C00915710":
    errors.append("Solomon extract used joint committee C00915710")
case = (donors.get("by_candidate") or {}).get("H2HI02128") or {}
if not (case.get("items") or [{}])[0].get("contributor_name"):
    errors.append("Case top donor name missing")

# Hawaii CSC
if hi.get("state_filings", {}).get("donors", {}).get("status") != "sourced":
    errors.append("hawaii.json state_filings.donors must be sourced")
if hi.get("state_filings", {}).get("csc_public") != "https://csc.hawaii.gov/CFSPublic/":
    errors.append("CFS public link missing")
if "view-searchable-data" not in (hi.get("state_filings", {}).get("csc_searchable") or ""):
    errors.append("CSC searchable landing missing")
if csc.get("row_count") != 18108:
    errors.append(f"csc row_count {csc.get('row_count')} != 18108")
if not csc.get("streets_omitted"):
    errors.append("csc-donors.json must omit street addresses")
street_keys = {"street", "address", "addr", "contributor_street_1", "contributor_street_2"}
for rec in (csc.get("by_candidate") or {}).values():
    for it in rec.get("items") or []:
        if street_keys & set(k.lower() for k in it.keys()):
            errors.append("csc-donors item has a street-address field")
            break
        if not it.get("source_url") or not it.get("retrieved_at"):
            errors.append("csc item missing source_url or retrieved_at")
            break
    else:
        continue
    break
unmatched = csc.get("unmatched_official_names") or []
if len(unmatched) != (csc.get("counts") or {}).get("unmatched"):
    errors.append("unmatched official names not kept/flagged")
iw = next((v for v in csc["by_candidate"].values() if v.get("matched_site_nominee") == "IWAMOTO, Kim Coco"), None)
if not iw or not iw.get("items"):
    errors.append("Iwamoto CSC match missing items")
if not csc.get("retrieved_at") or not csc.get("source_url"):
    errors.append("csc-donors.json missing source_url/retrieved_at")
if "hicscdata.hawaii.gov" not in (csc.get("source_url") or ""):
    errors.append("csc source_url should be official SODA")

congress = json.loads((ROOT / "congress-votes.json").read_text())
hivotes = json.loads((ROOT / "hawaii-votes.json").read_text())
if congress.get("row_count") != 200:
    errors.append(f"congress-votes row_count {congress.get('row_count')} != 200")
byc = congress.get("by_incumbent") or {}
for bio, n in {"C001055": 50, "T000487": 50, "H001042": 50, "S001194": 50}.items():
    got = (byc.get(bio) or {}).get("item_count_all")
    if got != n:
        errors.append(f"{bio} congress votes {got} != {n}")
case_items = (byc.get("C001055") or {}).get("items") or []
if not case_items or not case_items[0].get("vote_cast") or not case_items[0].get("source_url") or not case_items[0].get("retrieved_at"):
    errors.append("Case vote missing official vote_cast/source_url/retrieved_at")
def _urls(obj):
    out = []
    if isinstance(obj, dict):
        if obj.get("source_url"):
            out.append(str(obj.get("source_url")))
        for v in obj.values():
            out.extend(_urls(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_urls(v))
    return out

if any("ballotpedia" in u.lower() for u in _urls(congress) + _urls(hivotes)):
    errors.append("vote extracts must not use Ballotpedia")
if hivotes.get("row_count", 0) < 1 or not hivotes.get("by_member"):
    errors.append("hawaii-votes.json must not be empty")
if hivotes.get("unnamed_tallies_unexpanded") is not True:
    errors.append("hawaii-votes must keep unnamed tallies unexpanded")
iw = None
for rec in (hivotes.get("by_member") or {}).values():
    if rec.get("incumbent_name") == "Iwamoto":
        iw = rec
        break
if not iw:
    errors.append("Iwamoto missing from hawaii-votes")
else:
    hit = [
        i
        for i in iw.get("items") or []
        if i.get("measure") == "HB389" and "2026-04-23" in (i.get("vote_date") or "").replace("/", "-")
        or (i.get("measure") == "HB389" and i.get("vote_date") == "4/23/2026")
    ]
    if not any(i.get("vote_cast") == "Aye with reservations" for i in hit):
        errors.append(f"Iwamoto HB389 2026-04-23 aye with reservations missing: {hit[:2]}")
    for i in (iw.get("items") or [])[:1]:
        if not i.get("source_url") or not i.get("retrieved_at"):
            errors.append("Hawaii vote missing source_url/retrieved_at")
if (hivotes.get("sitting") or {}).get("house_names_seen") != 51:
    errors.append(f"house names seen {hivotes.get('sitting')} expected 51")
if hivotes.get("row_count") != 1241:
    flags = hivotes.get("disagreement_flags") or []
    if not any(f.get("field") == "named_votes" for f in flags):
        errors.append("hawaii named-vote count disagrees with 1241 freeze and is unflagged")

if errors:
    print("FAIL")
    for e in errors:
        print(" -", e)
    raise SystemExit(1)
print("OK gold ZIPs 96813, 90210, 82001")
print(
    "OK donors Case",
    case.get("item_count_all"),
    "Tokuda",
    donors["by_candidate"]["H2HI02581"]["item_count_all"],
    "CSC rows",
    csc.get("row_count"),
    "unmatched",
    len(unmatched),
)
print(
    "OK votes congress",
    congress.get("row_count"),
    "hawaii floor named",
    hivotes.get("row_count"),
)
