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
sd18v = hi["nominees"].get("State Senator, Dist 18 Vacancy") or []
if not any((n.get("name") or "") == "BASS, Danielle Maliekekai" for n in sd18v):
    errors.append("SD18 Vacancy OLVR nominee missing BASS, Danielle Maliekekai")
elif any("primary_votes" in n for n in sd18v if n.get("name") == "BASS, Danielle Maliekekai"):
    errors.append("Bass SD18 Vacancy must not invent primary_votes")

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
if congress.get("row_count") != 204:
    errors.append(f"congress-votes row_count {congress.get('row_count')} != 204")
byc = congress.get("by_incumbent") or {}
for bio, n in {"C001055": 52, "T000487": 52, "H001042": 50, "S001194": 50}.items():
    got = (byc.get(bio) or {}).get("item_count_all")
    if got != n:
        errors.append(f"{bio} congress votes {got} != {n}")
case_items = (byc.get("C001055") or {}).get("items") or []
if not case_items or not case_items[0].get("vote_cast") or not case_items[0].get("source_url") or not case_items[0].get("retrieved_at"):
    errors.append("Case vote missing official vote_cast/source_url/retrieved_at")
top = case_items[0] if case_items else {}
if top.get("roll_call_number") != 285 or top.get("vote_cast") != "Yea" or (top.get("measure") or "").replace(".", "").strip() != "S 32":
    errors.append(f"Case top item should be roll 285 Yea on S 32, got {top.get('roll_call_number')} {top.get('vote_cast')} {top.get('measure')}")
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

# Washington PDC Schedule A (50-state first populate; does not replace Hawaii)
wa_path = ROOT / "wa" / "pdc-donors.json"
wa_stub = ROOT / "wa.json"
if not wa_path.exists() or not wa_stub.exists():
    errors.append("WA PDC extract missing public/data/wa/pdc-donors.json or public/data/wa.json")
else:
    wa = json.loads(wa_path.read_text())
    wa_json = json.loads(wa_stub.read_text())
    donors_block = ((wa_json.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") != "sourced":
        errors.append("wa.json state_filings.donors.status must be sourced")
    if donors_block.get("path") != "/data/wa/pdc-donors.json":
        errors.append("wa.json donors.path must be /data/wa/pdc-donors.json")
    if wa.get("source_url") != "https://data.wa.gov/resource/kv7h-kjye.json":
        errors.append("pdc-donors.json source_url must be official data.wa.gov SODA kv7h-kjye")
    if "ballotpedia" in (wa.get("policy") or "").lower() and "no ballotpedia" not in (wa.get("policy") or "").lower():
        errors.append("WA policy must not use Ballotpedia")
    if any("ballotpedia" in u.lower() for u in _urls(wa) + _urls(wa_json)):
        errors.append("WA extract must not use Ballotpedia")
    if wa.get("row_count") != 151304 or (wa.get("counts") or {}).get("rows") != 151304:
        errors.append(f"WA row_count {wa.get('row_count')} != 151304")
    if wa.get("filer_count") != 1246 or len(wa.get("by_candidate") or {}) != 1246:
        errors.append(f"WA filer_count {wa.get('filer_count')} != 1246")
    if not wa.get("streets_omitted") or not wa.get("do_not_sell_donor_lists"):
        errors.append("WA extract must omit streets and say do_not_sell_donor_lists")
    if not wa.get("retrieved_at"):
        errors.append("pdc-donors.json missing retrieved_at")
    stokes = (wa.get("by_candidate") or {}).get("Andrew R Stokesbary (Drew Stokesbary)") or {}
    if not stokes or stokes.get("status") != "unmatched_no_roster" or stokes.get("matched_to_site") is not False:
        errors.append("Stokesbary PDC filer missing or incorrectly matched")
    if not (stokes.get("items") or []):
        errors.append("Stokesbary must keep official top contributions")
    if any("primary_votes" in (it or {}) for it in stokes.get("items") or []):
        errors.append("WA donor items must not invent primary_votes")
    wa_street = {"street", "address", "addr", "contributor_address", "contributor_street_1", "contributor_street_2", "contributor_zip", "contributor_location"}
    for rec in (wa.get("by_candidate") or {}).values():
        for it in rec.get("items") or []:
            if wa_street & {k.lower() for k in it}:
                errors.append("pdc-donors item has a street-address or exact-location field")
                break
            if not it.get("contributor_name"):
                errors.append("pdc-donors item missing official contributor_name")
                break
        else:
            continue
        break

# Colorado TRACER Schedule A (50-state first populate; does not replace HI/WA)
co_path = ROOT / "co" / "tracer-donors.json"
co_stub = ROOT / "co.json"
if not co_path.exists() or not co_stub.exists():
    errors.append("CO TRACER extract missing public/data/co/tracer-donors.json or public/data/co.json")
else:
    co = json.loads(co_path.read_text())
    co_json = json.loads(co_stub.read_text())
    donors_block = ((co_json.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") != "sourced":
        errors.append("co.json state_filings.donors.status must be sourced")
    if donors_block.get("path") != "/data/co/tracer-donors.json":
        errors.append("co.json donors.path must be /data/co/tracer-donors.json")
    if co.get("source_url") != "https://tracer.sos.colorado.gov/PublicSite/Docs/BulkDataDownloads/2026_ContributionData.csv.zip":
        errors.append("tracer-donors.json source_url must be official TRACER 2026 ContributionData ZIP")
    if "tracer.sos.colorado.gov" not in (co.get("landing_url") or ""):
        errors.append("tracer-donors.json landing_url must be official TRACER DataDownload")
    if any("ballotpedia" in u.lower() for u in _urls(co) + _urls(co_json)):
        errors.append("CO extract must not use Ballotpedia")
    if co.get("row_count") != 256892 or (co.get("counts") or {}).get("rows") != 256892:
        errors.append(f"CO row_count {co.get('row_count')} != 256892")
    if co.get("filer_count") != 1237 or len(co.get("by_candidate") or {}) != 1237:
        errors.append(f"CO filer_count {co.get('filer_count')} != 1237")
    if not co.get("streets_omitted") or not co.get("do_not_sell_donor_lists"):
        errors.append("CO extract must omit streets and say do_not_sell_donor_lists")
    if not co.get("retrieved_at"):
        errors.append("tracer-donors.json missing retrieved_at")
    bennet = (co.get("by_candidate") or {}).get("BENNET FOR GOVERNOR") or {}
    if not bennet or bennet.get("status") != "unmatched_no_roster" or bennet.get("matched_to_site") is not False:
        errors.append("BENNET FOR GOVERNOR TRACER filer missing or incorrectly matched")
    if not (bennet.get("items") or []):
        errors.append("BENNET FOR GOVERNOR must keep official top contributions")
    co_street = {"street", "address", "addr", "address1", "address2", "contributor_address", "zip", "zipcode", "contributor_zip"}
    for rec in (co.get("by_candidate") or {}).values():
        for it in rec.get("items") or []:
            if co_street & {k.lower() for k in it}:
                errors.append("tracer-donors item has a street-address or zip field")
                break
        else:
            continue
        break

# California SOS certified list + CA/WA federal votes (do not wipe HI/WA/CO donors)
ca_cands_path = ROOT / "ca" / "candidates.json"
ca_sum_path = ROOT / "ca" / "candidate-summary.json"
ca_votes_path = ROOT / "ca" / "votes.json"
wa_votes_path = ROOT / "wa" / "votes.json"
ca_json = json.loads((ROOT / "ca.json").read_text()) if (ROOT / "ca.json").exists() else {}
if not ca_cands_path.exists():
    errors.append("missing public/data/ca/candidates.json")
else:
    ca_cands = json.loads(ca_cands_path.read_text())
    if not isinstance(ca_cands, list) or len(ca_cands) != 388:
        errors.append(f"CA candidates.json rows {len(ca_cands) if isinstance(ca_cands, list) else type(ca_cands)} != 388")
    else:
        keys = {r.get("contest_key") for r in ca_cands}
        house = [r for r in ca_cands if r.get("office") == "United States Representative"]
        senate = [r for r in ca_cands if r.get("office") in {"State Senate", "State Senator"}]
        if any(not str(r.get("contest_key") or "").startswith("CA|") or str(r.get("contest_key") or "").count("|") != 3 for r in ca_cands):
            errors.append("CA contest_key must be CA|OFFICE|DIST|VACANCY")
        assembly = [r for r in ca_cands if r.get("office") == "State Assembly Member"]
        judicial = [r for r in ca_cands if "Justice" in (r.get("office") or "") or "Supreme Court" in (r.get("office") or "")]
        if len(keys) != 228:
            errors.append(f"CA contest_keys {len(keys)} != 228")
        if len(house) != 104 or {int(r["district"]) for r in house} != set(range(1, 53)):
            errors.append(f"CA US House {len(house)} dists {sorted({r.get('district') for r in house})}")
        if len(senate) != 40:
            errors.append(f"CA State Senate {len(senate)} != 40")
        if len(assembly) != 156:
            errors.append(f"CA Assembly {len(assembly)} != 156")
        if len(judicial) != 64:
            errors.append(f"CA judicial {len(judicial)} != 64")
        if any("senate" in (r.get("office") or "").lower() and "united states" in (r.get("office") or "").lower() for r in ca_cands):
            errors.append("CA certified list must not include U.S. Senate")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in ca_cands):
            errors.append("CA candidates must not use Ballotpedia")
        if any(r.get("list_kind") != "general_certified_pdf" for r in ca_cands):
            errors.append("CA candidates list_kind must be general_certified_pdf")
        if any(r.get("retrieved_at") != "2026-09-02T11:21:25Z" for r in ca_cands):
            errors.append("CA candidates retrieved_at must be 2026-09-02T11:21:25Z")
        if not any(r.get("candidate_name") == "Shirley N. Weber" and r.get("office") == "Secretary of State" for r in ca_cands):
            errors.append("CA SOS nominee Shirley N. Weber missing")
if ca_sum_path.exists():
    ca_sum = json.loads(ca_sum_path.read_text())
    if ca_sum.get("row_count") != 388 or ca_sum.get("contest_key_count") != 228:
        errors.append(f"CA candidate-summary counts {ca_sum}")
else:
    errors.append("missing public/data/ca/candidate-summary.json")
if ca_json.get("election", {}).get("general_date") != "2026-11-03":
    errors.append("ca.json election.general_date must be 2026-11-03")
if ca_json.get("candidates_path") != "/data/ca/candidates.json":
    errors.append("ca.json candidates_path missing")
if ca_json.get("votes_path") != "/data/ca/votes.json":
    errors.append("ca.json votes_path missing")
if ((ca_json.get("state_filings") or {}).get("donors") or {}).get("status") != "pending":
    errors.append("ca.json donors must remain pending Cal-Access")

def _check_votes(path, state, expected, members):
    if not path.exists():
        errors.append(f"missing {path}")
        return
    payload = json.loads(path.read_text())
    if payload.get("count") != expected or len(payload.get("votes") or []) != expected:
        errors.append(f"{state} votes count {payload.get('count')} != {expected}")
    if payload.get("state") != state:
        errors.append(f"{state} votes.json state field {payload.get('state')}")
    if any("ballotpedia" in (v.get("source_url") or "").lower() for v in payload.get("votes") or []):
        errors.append(f"{state} votes used Ballotpedia")
    if any(not v.get("vote_cast") or not v.get("source_url") or not v.get("retrieved_at") for v in (payload.get("votes") or [])[:3]):
        errors.append(f"{state} vote rows missing official vote_cast/source_url/retrieved_at")
    if any((v.get("district") or "") == "CA-14" for v in payload.get("votes") or []):
        errors.append("CA-14 vacant seat must be skipped")
    got_members = set((payload.get("counts_by_member") or {}).keys())
    if not members <= got_members:
        errors.append(f"{state} missing bioguides {sorted(members - got_members)}")

_check_votes(ca_votes_path, "CA", 2100, {"G000607", "V000130", "S001150", "P000145"})
_check_votes(wa_votes_path, "WA", 460, {"D000617", "S001159", "C000127", "M001111"})
if (ROOT / "wa.json").exists():
    waj = json.loads((ROOT / "wa.json").read_text())
    if ((waj.get("state_filings") or {}).get("donors") or {}).get("status") != "sourced":
        errors.append("wa.json donors were wiped")
    if waj.get("votes_path") != "/data/wa/votes.json":
        errors.append("wa.json votes_path not merged")
if (ROOT / "co.json").exists():
    if ((json.loads((ROOT / "co.json").read_text()).get("state_filings") or {}).get("donors") or {}).get("status") != "sourced":
        errors.append("co.json donors were wiped")

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
print("OK WA PDC rows", wa.get("row_count"), "filers", wa.get("filer_count"))
print("OK CO TRACER rows", co.get("row_count"), "filers", co.get("filer_count"))
print(
    "OK CA candidates",
    len(json.loads((ROOT / "ca" / "candidates.json").read_text())),
    "CA votes",
    json.loads((ROOT / "ca" / "votes.json").read_text()).get("count"),
    "WA votes",
    json.loads((ROOT / "wa" / "votes.json").read_text()).get("count"),
)
