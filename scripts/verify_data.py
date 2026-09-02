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
ca_donors_block = (ca_json.get("state_filings") or {}).get("donors") or {}
if ca_donors_block.get("status") != "sourced" or ca_donors_block.get("path") != "/data/ca/calaccess-donors.json":
    errors.append("ca.json donors must be sourced at /data/ca/calaccess-donors.json")
if not (ca_json.get("state_filings") or {}).get("wired"):
    errors.append("ca.json state_filings.wired must be true")
ca_donors_path = ROOT / "ca" / "calaccess-donors.json"
if not ca_donors_path.exists():
    errors.append("missing public/data/ca/calaccess-donors.json")
else:
    cad = json.loads(ca_donors_path.read_text())
    if cad.get("source_url") != "https://campaignfinance.cdn.sos.ca.gov/dbwebexport.zip":
        errors.append("calaccess-donors.json source_url must be official dbwebexport.zip")
    if cad.get("row_count") != 1928278:
        errors.append(f"CAL-ACCESS row_count {cad.get('row_count')} != 1928278")
    if not (2380 <= int(cad.get("filer_count") or 0) <= 2400):
        errors.append(f"CAL-ACCESS filer_count {cad.get('filer_count')} not ~2392")
    if not cad.get("streets_omitted") or not cad.get("do_not_sell_donor_lists"):
        errors.append("CAL-ACCESS extract must omit streets and say do_not_sell_donor_lists")
    if any("ballotpedia" in u.lower() for u in _urls(cad)):
        errors.append("CAL-ACCESS extract must not use Ballotpedia")
    ca_street = {"street", "address", "addr", "zip", "zipcode", "contributor_zip", "ctrib_zip4"}
    for rec in (cad.get("by_candidate") or {}).values():
        for it in rec.get("items") or []:
            if ca_street & {k.lower() for k in it}:
                errors.append("calaccess-donors item has a street-address or zip field")
                break
        else:
            continue
        break

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
    if ((waj.get("state_filings") or {}).get("donors") or {}).get("path") != "/data/wa/pdc-donors.json":
        errors.append("wa.json donors.path must stay /data/wa/pdc-donors.json")
    if waj.get("votes_path") != "/data/wa/votes.json":
        errors.append("wa.json votes_path not merged")
    if waj.get("candidates_path") != "/data/wa/candidates.json":
        errors.append("wa.json candidates_path missing")
    if waj.get("candidate_summary_path") != "/data/wa/candidate-summary.json":
        errors.append("wa.json candidate_summary_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(waj)):
        errors.append("wa.json must not use Ballotpedia")
wa_cands_path = ROOT / "wa" / "candidates.json"
wa_sum_path = ROOT / "wa" / "candidate-summary.json"
if not wa_cands_path.exists():
    errors.append("missing public/data/wa/candidates.json")
else:
    wa_cands = json.loads(wa_cands_path.read_text())
    if not isinstance(wa_cands, list) or len(wa_cands) != 887:
        errors.append(f"WA candidates.json rows {len(wa_cands) if isinstance(wa_cands, list) else type(wa_cands)} != 887")
    else:
        wa_keys = {r.get("contest_key") for r in wa_cands}
        # VoteWA GENERAL 2026 e=899 label is 599 offices / 887 candidates.
        if len(wa_keys) != 599:
            errors.append(f"WA contest_keys {len(wa_keys)} != 599 official offices")
        if any(not str(r.get("contest_key") or "").startswith("WA|") or str(r.get("contest_key") or "").count("|") != 3 for r in wa_cands):
            errors.append("WA contest_key must be WA|OFFICE|DIST|VACANCY")
        if any(r.get("list_kind") != "general_official" for r in wa_cands):
            errors.append("WA candidates list_kind must be general_official")
        if any(r.get("retrieved_at") != "2026-09-02T11:16:22Z" for r in wa_cands):
            errors.append("WA candidates retrieved_at must be 2026-09-02T11:16:22Z")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in wa_cands):
            errors.append("WA candidates must not use Ballotpedia")
        if any(r.get("source_url") != "https://voter.votewa.gov/CandidateList.aspx?e=899" for r in wa_cands):
            errors.append("WA candidates source_url must be official VoteWA e=899 list")
        house = [r for r in wa_cands if (r.get("office") or "") == "U.S. Representative"]
        if len(house) != 20 or {str(r.get("district")) for r in house} != {str(i) for i in range(1, 11)}:
            errors.append(f"WA US House {len(house)} dists {sorted({r.get('district') for r in house})}")
        if not any(r.get("candidate_name") == "Suzan DelBene" and r.get("district") == "1" for r in wa_cands):
            errors.append("WA nominee Suzan DelBene missing")
        countywide = [r for r in wa_cands if (r.get("district_raw") or "").casefold() == "county"]
        if len(countywide) != 421:
            errors.append(f"WA District=County rows {len(countywide)} != 421")
        if any(not r.get("county") for r in countywide):
            errors.append("WA District=County rows must recover county from VoteWA county filter")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in wa_cands):
            errors.append("WA candidates must omit streets/email/phone")
        if any(not r.get("race_id") or not r.get("candidate_id") for r in wa_cands):
            errors.append("WA candidates missing official VoteWA race_id/candidate_id")
if wa_sum_path.exists():
    wa_sum = json.loads(wa_sum_path.read_text())
    if wa_sum.get("row_count") != 887 or wa_sum.get("contest_key_count") != 599:
        errors.append(f"WA candidate-summary counts {wa_sum}")
else:
    errors.append("missing public/data/wa/candidate-summary.json")
if (ROOT / "co.json").exists():
    coj = json.loads((ROOT / "co.json").read_text())
    if ((coj.get("state_filings") or {}).get("donors") or {}).get("status") != "sourced":
        errors.append("co.json donors were wiped")
    if ((coj.get("state_filings") or {}).get("donors") or {}).get("path") != "/data/co/tracer-donors.json":
        errors.append("co.json donors.path must stay /data/co/tracer-donors.json")
    if ((coj.get("state_filings") or {}).get("donors") or {}).get("counts", {}).get("rows") != 256892:
        errors.append("co.json donor row count was changed")
    if coj.get("candidates_path") != "/data/co/candidates.json":
        errors.append("co.json candidates_path missing")
    if coj.get("candidate_summary_path") != "/data/co/candidate-summary.json":
        errors.append("co.json candidate_summary_path missing")
    if coj.get("votes_path") != "/data/co/votes.json":
        errors.append("co.json votes_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(coj)):
        errors.append("co.json must not use Ballotpedia")
co_cands_path = ROOT / "co" / "candidates.json"
co_sum_path = ROOT / "co" / "candidate-summary.json"
if not co_cands_path.exists():
    errors.append("missing public/data/co/candidates.json")
else:
    co_cands = json.loads(co_cands_path.read_text())
    if not isinstance(co_cands, list) or len(co_cands) != 661:
        errors.append(f"CO candidates.json rows {len(co_cands) if isinstance(co_cands, list) else type(co_cands)} != 661")
    else:
        if any(not str(r.get("contest_key") or "").startswith("CO|") or str(r.get("contest_key") or "").count("|") != 3 for r in co_cands):
            errors.append("CO contest_key must be CO|OFFICE|DIST|VACANCY")
        kinds = {r.get("list_kind") for r in co_cands}
        if kinds != {"primary_official", "general_unofficial"}:
            errors.append(f"CO list_kind set {kinds}")
        primary = [r for r in co_cands if r.get("list_kind") == "primary_official"]
        general = [r for r in co_cands if r.get("list_kind") == "general_unofficial"]
        if len(primary) != 251 or len(general) != 410:
            errors.append(f"CO primary/general split {len(primary)}/{len(general)}")
        gen_keys = {r.get("contest_key") for r in general}
        if len(gen_keys) != 166:
            errors.append(f"CO general contest_keys {len(gen_keys)} != 166")
        if any(r.get("retrieved_at") != "2026-09-02T11:12:00Z" for r in co_cands):
            errors.append("CO candidates retrieved_at must be 2026-09-02T11:12:00Z")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in co_cands):
            errors.append("CO candidates must not use Ballotpedia")
        if any("sos.state.co.us" not in (r.get("source_url") or "") for r in co_cands):
            errors.append("CO candidates source_url must be official SOS Excel")
        if not any(r.get("candidate_name") == "John Hickenlooper" and r.get("office") == "US Senate" and r.get("list_kind") == "general_unofficial" for r in co_cands):
            errors.append("CO general list missing filed name John Hickenlooper")
        if not any(r.get("candidate_name") == "Diana DeGette" for r in co_cands):
            errors.append("CO list missing filed name Diana DeGette")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in co_cands):
            errors.append("CO candidates must omit streets/email/phone")
if co_sum_path.exists():
    co_sum = json.loads(co_sum_path.read_text())
    if co_sum.get("row_count") != 661 or co_sum.get("contest_key_count") != 166:
        errors.append(f"CO candidate-summary counts {co_sum}")
else:
    errors.append("missing public/data/co/candidate-summary.json")
_check_votes(ROOT / "co" / "votes.json", "CO", 380, {"D000197", "B001267", "H000273", "N000191"})

# Oregon ORESTAR filings + Clerk/LIS votes (donors pending/blocked; no free statewide bulk)
or_stub_path = ROOT / "or.json"
or_cands_path = ROOT / "or" / "candidates.json"
or_sum_path = ROOT / "or" / "candidate-summary.json"
or_votes_path = ROOT / "or" / "votes.json"
if not or_stub_path.exists():
    errors.append("missing public/data/or.json")
else:
    orj = json.loads(or_stub_path.read_text())
    donors_block = ((orj.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") not in {"pending", "blocked"}:
        errors.append("or.json donors.status must be pending/blocked (no free statewide bulk)")
    if donors_block.get("path"):
        errors.append("or.json must not invent a donor extract path")
    if not donors_block.get("do_not_sell_donor_lists"):
        errors.append("or.json donors must say do_not_sell_donor_lists")
    reason = (donors_block.get("reason") or "").lower()
    if "orestar" not in reason and "statewide" not in reason and "bulk" not in reason:
        errors.append("or.json donors.reason must honestly say no free ORESTAR/statewide bulk")
    if orj.get("election", {}).get("state_code") != "OR" or orj.get("election", {}).get("jurisdiction") != "Oregon":
        errors.append("or.json election must be Oregon / OR")
    if orj.get("candidates_path") != "/data/or/candidates.json":
        errors.append("or.json candidates_path missing")
    if orj.get("candidate_summary_path") != "/data/or/candidate-summary.json":
        errors.append("or.json candidate_summary_path missing")
    if orj.get("votes_path") != "/data/or/votes.json":
        errors.append("or.json votes_path missing")
    if orj.get("congress_delegation_path") != "/data/or/congress-delegation.json":
        errors.append("or.json congress_delegation_path missing")
    if orj.get("legislature_vote_index_path") != "/data/or/legislature-vote-index.json":
        errors.append("or.json legislature_vote_index_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(orj)):
        errors.append("or.json must not use Ballotpedia")
if (ROOT / "or" / "pdc-donors.json").exists() or (ROOT / "or" / "orestar-donors.json").exists():
    errors.append("OR must not invent a donor extract")
if not or_cands_path.exists():
    errors.append("missing public/data/or/candidates.json")
else:
    or_cands = json.loads(or_cands_path.read_text())
    if not isinstance(or_cands, list) or len(or_cands) != 604:
        errors.append(f"OR candidates.json rows {len(or_cands) if isinstance(or_cands, list) else type(or_cands)} != 604")
    else:
        if any(not str(r.get("contest_key") or "").startswith("OR|") or str(r.get("contest_key") or "").count("|") != 3 for r in or_cands):
            errors.append("OR contest_key must be OR|OFFICE|DIST|VACANCY")
        kinds = {r.get("list_kind") for r in or_cands}
        if kinds != {"primary_candidate_filing", "general_candidate_filing"}:
            errors.append(f"OR list_kind set {kinds}")
        primary = [r for r in or_cands if r.get("list_kind") == "primary_candidate_filing"]
        general = [r for r in or_cands if r.get("list_kind") == "general_candidate_filing"]
        if len(primary) != 343 or len(general) != 261:
            errors.append(f"OR primary/general split {len(primary)}/{len(general)}")
        keys = {r.get("contest_key") for r in or_cands}
        if len(keys) != 166:
            errors.append(f"OR contest_keys {len(keys)} != 166")
        if any(r.get("retrieved_at") != "2026-09-02T11:20:30Z" for r in or_cands):
            errors.append("OR candidates retrieved_at must be 2026-09-02T11:20:30Z")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in or_cands):
            errors.append("OR candidates must not use Ballotpedia")
        if any("sos.state.or.us/orestar" not in (r.get("source_url") or "") for r in or_cands):
            errors.append("OR candidates source_url must be official ORESTAR CFSearch")
        if any(not r.get("election") or not r.get("election_year") or not r.get("election_id") for r in or_cands):
            errors.append("OR candidates must keep election fields")
        if not any(r.get("candidate_name") == "Jeff Merkley" and r.get("office") == "US Senator" for r in or_cands):
            errors.append("OR list missing filed name Jeff Merkley")
        if not any(r.get("candidate_name") == "Suzanne Bonamici" for r in or_cands):
            errors.append("OR list missing filed name Suzanne Bonamici")
        if not any(r.get("candidate_name") == "Tina Kotek" and r.get("office") == "Governor" for r in or_cands):
            errors.append("OR list missing filed name Tina Kotek")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone", "cell", "web_address"}
        if any(street_keys & {k.lower() for k in r} for r in or_cands):
            errors.append("OR candidates must omit streets/email/phone")
if or_sum_path.exists():
    or_sum = json.loads(or_sum_path.read_text())
    if or_sum.get("row_count") != 604 or or_sum.get("contest_key_count") != 166:
        errors.append(f"OR candidate-summary counts {or_sum}")
else:
    errors.append("missing public/data/or/candidate-summary.json")
_check_votes(or_votes_path, "OR", 300, {"B001278", "B000668", "D000635", "H001094", "B001326", "S001226", "M001176", "W000779"})
if (ROOT / "or" / "legislature-vote-index.json").exists():
    or_idx = json.loads((ROOT / "or" / "legislature-vote-index.json").read_text())
    if or_idx.get("kind") != "legislature_vote_index":
        errors.append("OR legislature-vote-index must be URL index only")
    if any("ballotpedia" in (s.get("url") or "").lower() for s in or_idx.get("sources") or []):
        errors.append("OR legislature index must not use Ballotpedia")
    if not any("oregonlegislature.gov" in (s.get("url") or "") for s in or_idx.get("sources") or []):
        errors.append("OR legislature index must cite official oregonlegislature.gov")
else:
    errors.append("missing public/data/or/legislature-vote-index.json")

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
    "CA CAL-ACCESS filers",
    json.loads((ROOT / "ca" / "calaccess-donors.json").read_text()).get("filer_count"),
    "WA ballots",
    len(json.loads((ROOT / "wa" / "candidates.json").read_text())),
    "CO ballots",
    len(json.loads((ROOT / "co" / "candidates.json").read_text())),
    "CO votes",
    json.loads((ROOT / "co" / "votes.json").read_text()).get("count"),
    "OR ballots",
    len(json.loads((ROOT / "or" / "candidates.json").read_text())),
    "OR votes",
    json.loads((ROOT / "or" / "votes.json").read_text()).get("count"),
)
