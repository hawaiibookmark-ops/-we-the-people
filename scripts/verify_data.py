#!/usr/bin/env python3
"""Sanity-check gold-template ZIPs and committed donor extracts."""
import json
from collections import Counter
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
kit = next((n for n in sd18v if (n.get("name") or "") == "KITASHIMA, Kelly Puamailani"), None)
if not kit:
    errors.append("SD18 Vacancy OLVR nominee missing KITASHIMA, Kelly Puamailani")
else:
    if kit.get("party_code") != "R" or "Republican" not in (kit.get("party") or ""):
        errors.append("Kitashima must be Republican from official OLVR")
    if kit.get("status") != "In General":
        errors.append("Kitashima OLVR status must be In General")
    if "primary_votes" in kit:
        errors.append("Kitashima SD18 Vacancy must not invent primary_votes")
    if "olvr.hawaii.gov" not in (kit.get("source_url") or ""):
        errors.append("Kitashima must cite official OLVR candidate report")
    kit_donors = kit.get("donors") or {}
    if kit_donors.get("status") != "empty" or kit_donors.get("item_count_all") != 0:
        errors.append("Kitashima hawaii.json donors must stay CSC honest-empty (0 rows)")
    if kit_donors.get("items"):
        errors.append("Kitashima must not invent CSC receipts")
    if kit_donors.get("retrieved_at") != "2026-09-03T21:08:29Z":
        errors.append("Kitashima donor retrieved_at must be weekday refresh 2026-09-03T21:08:29Z")
    if not kit_donors.get("do_not_sell_donor_lists"):
        errors.append("Kitashima donors must say do_not_sell_donor_lists")

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
hi_donor_counts = (hi.get("state_filings", {}).get("donors") or {}).get("counts") or {}
if hi_donor_counts.get("rows") != 18875:
    errors.append(f"hawaii.json CSC counts.rows {hi_donor_counts.get('rows')} != 18875")
if (hi.get("state_filings", {}).get("donors") or {}).get("retrieved_at") != "2026-09-03T21:08:29Z":
    errors.append("hawaii.json CSC retrieved_at must be weekday refresh 2026-09-03T21:08:29Z")
if (hi.get("state_filings", {}).get("donors") or {}).get("path") != "/data/csc-donors.json":
    errors.append("hawaii.json CSC path must stay /data/csc-donors.json")
if ((hi.get("state_filings", {}).get("donors") or {}).get("counts") or {}).get("empty") != 1:
    errors.append("hawaii.json CSC counts.empty must be 1 (Kitashima honest-empty)")
if ((hi.get("state_filings", {}).get("donors") or {}).get("counts") or {}).get("candidates") != 248:
    errors.append("hawaii.json CSC counts.candidates must be 248 after Kitashima empty")
if hi.get("state_filings", {}).get("csc_public") != "https://csc.hawaii.gov/CFSPublic/":
    errors.append("CFS public link missing")
if "view-searchable-data" not in (hi.get("state_filings", {}).get("csc_searchable") or ""):
    errors.append("CSC searchable landing missing")
if csc.get("row_count") != 18875:
    errors.append(f"csc row_count {csc.get('row_count')} != 18875")
if csc.get("retrieved_at") != "2026-09-03T21:08:29Z":
    errors.append(f"csc retrieved_at {csc.get('retrieved_at')} != 2026-09-03T21:08:29Z")
if csc.get("candidate_count") != 248 or (csc.get("counts") or {}).get("candidates") != 248:
    errors.append(f"csc candidate_count {csc.get('candidate_count')} != 248")
if (csc.get("counts") or {}).get("empty") != 1:
    errors.append("csc counts.empty must be 1 after Kitashima honest-empty")
kit_csc = next(
    (v for v in (csc.get("by_candidate") or {}).values() if v.get("matched_site_nominee") == "KITASHIMA, Kelly Puamailani"),
    None,
)
if not kit_csc:
    errors.append("csc-donors.json missing Kitashima matched empty row")
else:
    if kit_csc.get("status") != "empty" or kit_csc.get("item_count_all") != 0 or kit_csc.get("items"):
        errors.append("Kitashima CSC row must stay status=empty with 0 items")
    if kit_csc.get("reg_no") in {"CC11342", "cc11342"}:
        errors.append("Kitashima must not reuse 2014-2018 Honolulu Council CC11342 receipts")
    if kit_csc.get("retrieved_at") != "2026-09-03T21:08:29Z":
        errors.append("Kitashima CSC retrieved_at must be 2026-09-03T21:08:29Z")
if not csc.get("do_not_sell_donor_lists"):
    errors.append("csc-donors.json must say do_not_sell_donor_lists")
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
if congress.get("row_count") != 218:
    errors.append(f"congress-votes row_count {congress.get('row_count')} != 218")
byc = congress.get("by_incumbent") or {}
for bio, n in {"C001055": 59, "T000487": 59, "H001042": 50, "S001194": 50}.items():
    got = (byc.get(bio) or {}).get("item_count_all")
    if got != n:
        errors.append(f"{bio} congress votes {got} != {n}")
case_items = (byc.get("C001055") or {}).get("items") or []
if not case_items or not case_items[0].get("vote_cast") or not case_items[0].get("source_url") or not case_items[0].get("retrieved_at"):
    errors.append("Case vote missing official vote_cast/source_url/retrieved_at")
top = case_items[0] if case_items else {}
if top.get("roll_call_number") != 292 or top.get("vote_cast") != "Yea" or "1498" not in (top.get("measure") or ""):
    errors.append(f"Case top item should be roll 292 Yea on H RES 1498, got {top.get('roll_call_number')} {top.get('vote_cast')} {top.get('measure')}")
hirono_top = ((byc.get("H001042") or {}).get("items") or [{}])[0]
if hirono_top.get("roll_call_number") != 231:
    errors.append(f"Senate latest must stay 231, got {hirono_top.get('roll_call_number')}")
# Official Clerk text is Yea/Nay/No — do not normalize roll 288 "No" to Nay.
tokuda_288 = next((i for i in (byc.get("T000487") or {}).get("items") or [] if i.get("roll_call_number") == 288), None)
if not tokuda_288 or tokuda_288.get("vote_cast") != "No":
    errors.append(f"Tokuda roll 288 must keep official vote_cast No, got {tokuda_288}")
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
    if donors_block.get("status") not in {"sourced", "partial"}:
        errors.append("or.json donors.status must be sourced/partial (federal FEC Schedule A $200+)")
    if donors_block.get("path") != "/data/or/fec-donors.json":
        errors.append("or.json donors.path must be /data/or/fec-donors.json")
    if donors_block.get("source_url") != "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip":
        errors.append("or.json donors.source_url must be official indiv26.zip")
    if not donors_block.get("do_not_sell_donor_lists"):
        errors.append("or.json donors must say do_not_sell_donor_lists")
    scope = ((donors_block.get("scope") or "") + " " + (donors_block.get("reason") or "")).lower()
    if "orestar" not in scope or "fec" not in scope:
        errors.append("or.json donors must say federal FEC only and ORESTAR still blocked")
    counts = donors_block.get("counts") or {}
    if counts.get("candidates") != 40 or counts.get("kept_rows") != 7522:
        errors.append(f"or.json donor counts {counts} != 40 candidates / 7522 kept rows")
    if donors_block.get("retrieved_at") != "2026-09-02T12:14:47Z":
        errors.append("or.json donors.retrieved_at must be 2026-09-02T12:14:47Z")
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
    errors.append("OR must not invent a state ORESTAR/PDC donor extract")
or_fec_path = ROOT / "or" / "fec-donors.json"
if not or_fec_path.exists():
    errors.append("missing public/data/or/fec-donors.json")
else:
    orfec = json.loads(or_fec_path.read_text())
    if orfec.get("source_url") != "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip":
        errors.append("or/fec-donors.json source_url must be official indiv26.zip")
    if orfec.get("fec_api_key_present"):
        errors.append("or/fec-donors.json must not use OpenFEC/DEMO_KEY")
    if orfec.get("row_count") != 7522 or (orfec.get("counts") or {}).get("kept_rows") != 7522:
        errors.append(f"OR FEC kept_rows {orfec.get('row_count')} != 7522")
    if orfec.get("candidate_count") != 40 or len(orfec.get("by_candidate") or {}) != 40:
        errors.append(f"OR FEC candidates {orfec.get('candidate_count')} != 40")
    with_n = sum(1 for v in (orfec.get("by_candidate") or {}).values() if (v.get("item_count_all") or 0) > 0)
    empty_n = sum(1 for v in (orfec.get("by_candidate") or {}).values() if (v.get("item_count_all") or 0) == 0)
    if with_n != 25 or empty_n != 15:
        errors.append(f"OR FEC with/empty {with_n}/{empty_n} != 25/15")
    if not orfec.get("do_not_sell_donor_lists") or not orfec.get("streets_omitted"):
        errors.append("OR FEC extract must omit streets and say do_not_sell_donor_lists")
    if orfec.get("retrieved_at") != "2026-09-02T12:14:47Z":
        errors.append("OR FEC retrieved_at must be 2026-09-02T12:14:47Z")
    if any("ballotpedia" in u.lower() for u in _urls(orfec)):
        errors.append("OR FEC extract must not use Ballotpedia")
    if any("open.fec.gov" in u.lower() for u in _urls(orfec)):
        errors.append("OR FEC extract must not use OpenFEC")
    merk = (orfec.get("by_candidate") or {}).get("S8OR00207") or {}
    if merk.get("candidate_name") != "MERKLEY, JEFFREY ALAN" or not (merk.get("items") or []):
        errors.append("Merkley FEC extract missing official name/items")
    if (merk.get("items") or [{}])[0].get("contributor_name") is None:
        errors.append("Merkley top donor name missing")
    sol = (orfec.get("by_candidate") or {}).get("S6OR05226") or {}
    if sol.get("committee_id"):
        errors.append("OR Solomon must have no PCC (do not use joint C00915710)")
    house_perkins = (orfec.get("by_candidate") or {}).get("H6OR04203") or {}
    senate_perkins = (orfec.get("by_candidate") or {}).get("S4OR00156") or {}
    if (house_perkins.get("item_count_all") or 0) != 0 or (senate_perkins.get("item_count_all") or 0) != 9:
        errors.append("shared Perkins PCC must be assigned once via ccl26 P (Senate 9 / House 0)")
    or_street = {"street", "address", "addr", "zip", "zipcode", "contributor_zip", "occupation"}
    for rec in (orfec.get("by_candidate") or {}).values():
        for it in rec.get("items") or []:
            if or_street & {k.lower() for k in it}:
                errors.append("or/fec-donors item has a street-address or zip field")
                break
            if not it.get("contributor_name") or it.get("amount") is None:
                errors.append("or/fec-donors item missing official contributor_name/amount")
                break
        else:
            continue
        break
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

# Arizona primary nominations PDF + Clerk/LIS votes + federal FEC partial donors
az_stub_path = ROOT / "az.json"
az_cands_path = ROOT / "az" / "candidates.json"
az_sum_path = ROOT / "az" / "candidate-summary.json"
az_votes_path = ROOT / "az" / "votes.json"
az_fec_path = ROOT / "az" / "fec-donors.json"
if not az_stub_path.exists():
    errors.append("missing public/data/az.json")
else:
    azj = json.loads(az_stub_path.read_text())
    donors_block = ((azj.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") != "partial":
        errors.append("az.json donors.status must be partial (federal FEC only)")
    if donors_block.get("path") != "/data/az/fec-donors.json":
        errors.append("az.json donors.path must be /data/az/fec-donors.json")
    if donors_block.get("source_url") != "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip":
        errors.append("az.json donors.source_url must be official indiv26.zip")
    if not donors_block.get("do_not_sell_donor_lists"):
        errors.append("az.json donors must say do_not_sell_donor_lists")
    scope = (donors_block.get("scope") or "").lower()
    if "fec" not in scope or ("prr" not in scope and "seethemoney" not in scope):
        errors.append("az.json donors.scope must say federal FEC only and state bulk blocked")
    counts = donors_block.get("counts") or {}
    if counts.get("candidates") != 92 or counts.get("kept_rows") != 19688:
        errors.append(f"az.json donor counts {counts} != 92 / 19688")
    note = (azj.get("election") or {}).get("note") or ""
    if "primary" not in note.lower() or "nominations" not in note.lower():
        errors.append("az.json election.note must label primary nominations/petitions filed")
    if "general" not in note.lower() and "certified" not in note.lower() and "apps.arizona.vote" not in note.lower():
        errors.append("az.json must say this is not a general certified list / CF-blocked")
    if azj.get("election", {}).get("state_code") != "AZ":
        errors.append("az.json election must be Arizona / AZ")
    if azj.get("candidates_path") != "/data/az/candidates.json":
        errors.append("az.json candidates_path missing")
    if azj.get("candidate_summary_path") != "/data/az/candidate-summary.json":
        errors.append("az.json candidate_summary_path missing")
    if azj.get("votes_path") != "/data/az/votes.json":
        errors.append("az.json votes_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(azj)):
        errors.append("az.json must not use Ballotpedia")
if not az_cands_path.exists():
    errors.append("missing public/data/az/candidates.json")
else:
    az_cands = json.loads(az_cands_path.read_text())
    if not isinstance(az_cands, list) or len(az_cands) != 266:
        errors.append(f"AZ candidates.json rows {len(az_cands) if isinstance(az_cands, list) else type(az_cands)} != 266")
    else:
        if any(not str(r.get("contest_key") or "").startswith("AZ|") or str(r.get("contest_key") or "").count("|") != 3 for r in az_cands):
            errors.append("AZ contest_key must be AZ|OFFICE|DIST|VACANCY")
        if {r.get("list_kind") for r in az_cands} != {"primary_nominations_petitions_filed"}:
            errors.append("AZ list_kind must be primary_nominations_petitions_filed")
        keys = {r.get("contest_key") for r in az_cands}
        if len(keys) != 76:
            errors.append(f"AZ contest_keys {len(keys)} != 76")
        if any(r.get("retrieved_at") != "2026-09-02T11:23:07Z" for r in az_cands):
            errors.append("AZ candidates retrieved_at must be 2026-09-02T11:23:07Z")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in az_cands):
            errors.append("AZ candidates must not use Ballotpedia")
        if any("azsos.gov" not in (r.get("source_url") or "") for r in az_cands):
            errors.append("AZ candidates source_url must be official azsos.gov PDF")
        if not any(r.get("candidate_name") == "Hobbs, Katie" and r.get("office") == "Governor" for r in az_cands):
            errors.append("AZ list missing filed name Hobbs, Katie")
        if not any(r.get("candidate_name") == "Gosar, Paul" for r in az_cands):
            errors.append("AZ list missing filed name Gosar, Paul")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in az_cands):
            errors.append("AZ candidates must omit streets/email/phone")
if az_sum_path.exists():
    az_sum = json.loads(az_sum_path.read_text())
    if az_sum.get("row_count") != 266 or az_sum.get("contest_key_count") != 76:
        errors.append(f"AZ candidate-summary counts {az_sum}")
else:
    errors.append("missing public/data/az/candidate-summary.json")
_check_votes(az_votes_path, "AZ", 420, {"G000574", "S001211", "K000377", "G000565"})
if not az_fec_path.exists():
    errors.append("missing public/data/az/fec-donors.json")
else:
    azfec = json.loads(az_fec_path.read_text())
    if azfec.get("source_url") != "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip":
        errors.append("az/fec-donors.json source_url must be official indiv26.zip")
    if azfec.get("fec_api_key_present"):
        errors.append("az/fec-donors.json must not use OpenFEC/DEMO_KEY")
    if azfec.get("row_count") != 19688 or (azfec.get("counts") or {}).get("kept_rows") != 19688:
        errors.append(f"AZ FEC kept_rows {azfec.get('row_count')} != 19688")
    if azfec.get("candidate_count") != 92 or len(azfec.get("by_candidate") or {}) != 92:
        errors.append(f"AZ FEC candidates {azfec.get('candidate_count')} != 92")
    with_n = sum(1 for v in (azfec.get("by_candidate") or {}).values() if (v.get("item_count_all") or 0) > 0)
    empty_n = sum(1 for v in (azfec.get("by_candidate") or {}).values() if (v.get("item_count_all") or 0) == 0)
    if with_n != 47 or empty_n != 45:
        errors.append(f"AZ FEC with/empty {with_n}/{empty_n} != 47/45")
    if not azfec.get("do_not_sell_donor_lists") or not azfec.get("streets_omitted"):
        errors.append("AZ FEC extract must omit streets and say do_not_sell_donor_lists")
    if azfec.get("retrieved_at") != "2026-09-02T12:21:44Z":
        errors.append("AZ FEC retrieved_at must be 2026-09-02T12:21:44Z")
    if any("ballotpedia" in u.lower() or "open.fec.gov" in u.lower() for u in _urls(azfec)):
        errors.append("AZ FEC extract must not use Ballotpedia or OpenFEC")
    gosar = (azfec.get("by_candidate") or {}).get("H0AZ01259") or {}
    if gosar.get("candidate_name") != "GOSAR, PAUL DR." or not (gosar.get("items") or []):
        errors.append("Gosar FEC extract missing official name/items")

# Michigan MiTN Schedule A (optional until that package lands; do not wipe when present)
mi_path = ROOT / "mi" / "mitn-donors.json"
mi_stub = ROOT / "mi.json"
if mi_path.exists() and mi_stub.exists():
    mi = json.loads(mi_path.read_text())
    mi_json = json.loads(mi_stub.read_text())
    donors_block = ((mi_json.get("state_filings") or {}).get("donors") or {})
    if not (mi_json.get("state_filings") or {}).get("wired"):
        errors.append("mi.json state_filings.wired must be true")
    if donors_block.get("status") != "sourced":
        errors.append("mi.json state_filings.donors.status must be sourced")
    if donors_block.get("path") != "/data/mi/mitn-donors.json":
        errors.append("mi.json donors.path must be /data/mi/mitn-donors.json")
    if donors_block.get("counts", {}).get("rows") != 964108 or donors_block.get("counts", {}).get("filers") != 1378:
        errors.append(f"mi.json donor counts {donors_block.get('counts')}")
    if donors_block.get("counts", {}).get("items_per_filer_cap") != 25:
        errors.append("mi.json items_per_filer_cap must be 25")
    if donors_block.get("counts", {}).get("election_year") != 2026:
        errors.append("mi.json election_year must be 2026")
    if not donors_block.get("do_not_sell_donor_lists"):
        errors.append("mi.json must say do_not_sell_donor_lists")
    if "id=21077" not in (mi.get("source_url") or "") or "mi-boe.entellitrak.com" not in (mi.get("source_url") or ""):
        errors.append("mitn-donors.json source_url must be official MiTN ZIP id 21077")
    if "cfrexportdownload" not in (mi.get("landing_url") or "") or "mi-boe.entellitrak.com" not in (mi.get("landing_url") or ""):
        errors.append("mitn-donors.json landing_url must be official MiTN download page")
    if any("ballotpedia" in u.lower() for u in _urls(mi) + _urls(mi_json)):
        errors.append("MI extract must not use Ballotpedia")
    if mi.get("row_count") != 964108 or (mi.get("counts") or {}).get("rows") != 964108:
        errors.append(f"MI row_count {mi.get('row_count')} != 964108")
    if mi.get("filer_count") != 1378 or len(mi.get("by_candidate") or {}) != 1378:
        errors.append(f"MI filer_count {mi.get('filer_count')} != 1378")
    if not mi.get("streets_omitted") or not mi.get("do_not_sell_donor_lists"):
        errors.append("MI extract must omit streets and say do_not_sell_donor_lists")
    if mi.get("retrieved_at") != "2026-09-02T13:00:04Z":
        errors.append("mitn-donors.json retrieved_at must be 2026-09-02T13:00:04Z")
    if mi_json.get("election", {}).get("state_code") != "MI" or mi_json.get("election", {}).get("jurisdiction") != "Michigan":
        errors.append("mi.json election must be Michigan / MI")
    if mi_json.get("nominees") != {} or mi_json.get("geo_by_zip") != {}:
        errors.append("mi.json nominees/geo must stay empty (use candidates_path)")
    benson = (mi.get("by_candidate") or {}).get("JOCELYN BENSON FOR GOVERNOR") or {}
    if not benson or benson.get("status") != "unmatched_no_roster" or benson.get("matched_to_site") is not False:
        errors.append("JOCELYN BENSON FOR GOVERNOR MiTN filer missing or incorrectly matched")
    if not (benson.get("items") or []):
        errors.append("JOCELYN BENSON FOR GOVERNOR must keep official top contributions")
    if any("primary_votes" in (it or {}) for it in benson.get("items") or []):
        errors.append("MI donor items must not invent primary_votes")
    mi_street = {
        "street",
        "address",
        "addr",
        "address1",
        "address2",
        "contributor_address",
        "zip",
        "zipcode",
        "contributor_zip",
    }
    for rec in (mi.get("by_candidate") or {}).values():
        for it in rec.get("items") or []:
            if mi_street & {k.lower() for k in it}:
                errors.append("mitn-donors item has a street-address or zip field")
                break
        else:
            continue
        break

# Illinois SBE Schedule A (does not replace HI/WA/CO/CA/OR/AZ/MI)
il_path = ROOT / "il" / "sbe-donors.json"
il_stub = ROOT / "il.json"
if not il_path.exists() or not il_stub.exists():
    errors.append("IL SBE extract missing public/data/il/sbe-donors.json or public/data/il.json")
else:
    il = json.loads(il_path.read_text())
    il_json = json.loads(il_stub.read_text())
    donors_block = ((il_json.get("state_filings") or {}).get("donors") or {})
    fec_block = ((il_json.get("state_filings") or {}).get("federal_fec") or {})
    if not (il_json.get("state_filings") or {}).get("wired"):
        errors.append("il.json state_filings.wired must be true")
    if donors_block.get("status") != "sourced":
        errors.append("il.json state_filings.donors.status must be sourced")
    if donors_block.get("path") != "/data/il/sbe-donors.json":
        errors.append("il.json donors.path must be /data/il/sbe-donors.json")
    if donors_block.get("counts", {}).get("rows") != 191759 or donors_block.get("counts", {}).get("filers") != 2851:
        errors.append(f"il.json donor counts {donors_block.get('counts')}")
    if not donors_block.get("do_not_sell_donor_lists"):
        errors.append("il.json must say do_not_sell_donor_lists")
    if fec_block.get("path") != "/data/il/fec-donors.json" or fec_block.get("status") != "partial":
        errors.append("il.json federal_fec must stay partial at /data/il/fec-donors.json")
    fec_counts = fec_block.get("counts") or {}
    if fec_counts.get("candidates") != 189 or fec_counts.get("kept_rows") != 48312:
        errors.append(f"il.json federal_fec counts {fec_counts} != 189 / 48312")
    if il_json.get("candidates_path") != "/data/il/candidates.json":
        errors.append("il.json candidates_path missing")
    if il_json.get("votes_path") != "/data/il/votes.json":
        errors.append("il.json votes_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(il_json)):
        errors.append("il.json must not use Ballotpedia")
    if il.get("source_url") != "https://downloads.elections.il.gov/Receipts.txt":
        errors.append("sbe-donors.json source_url must be official downloads.elections.il.gov/Receipts.txt")
    if "DownloadCDDataFiles" not in (il.get("landing_url") or ""):
        errors.append("sbe-donors.json landing_url must be official SBE DownloadCDDataFiles")
    if any("ballotpedia" in u.lower() for u in _urls(il) + _urls(il_json)):
        errors.append("IL extract must not use Ballotpedia")
    if il.get("row_count") != 191759 or (il.get("counts") or {}).get("rows") != 191759:
        errors.append(f"IL row_count {il.get('row_count')} != 191759")
    if il.get("filer_count") != 2851 or len(il.get("by_candidate") or {}) != 2851:
        errors.append(f"IL filer_count {il.get('filer_count')} != 2851")
    if not il.get("streets_omitted") or not il.get("do_not_sell_donor_lists"):
        errors.append("IL extract must omit streets and say do_not_sell_donor_lists")
    if il.get("retrieved_at") != "2026-09-02T13:26:08Z":
        errors.append("sbe-donors.json retrieved_at must be 2026-09-02T13:26:08Z")
    if il_json.get("election", {}).get("state_code") != "IL" or il_json.get("election", {}).get("jurisdiction") != "Illinois":
        errors.append("il.json election must be Illinois / IL")
    election_note = (il_json.get("election") or {}).get("note") or ""
    if "RSS-partial" not in election_note or "Candidates.txt TBD" not in election_note:
        errors.append("il.json election note must say RSS-partial and Candidates.txt TBD")
    jb = (il.get("by_candidate") or {}).get("JB for Governor") or {}
    if not jb or jb.get("status") != "unmatched_no_roster" or jb.get("matched_to_site") is not False:
        errors.append("JB for Governor SBE filer missing or incorrectly matched")
    if not (jb.get("items") or []):
        errors.append("JB for Governor must keep official top contributions")
    il_street = {
        "street",
        "address",
        "addr",
        "address1",
        "address2",
        "contributor_address",
        "zip",
        "zipcode",
        "contributor_zip",
    }
    for rec in (il.get("by_candidate") or {}).values():
        for it in rec.get("items") or []:
            if il_street & {k.lower() for k in it}:
                errors.append("sbe-donors item has a street-address or zip field")
                break
        else:
            continue
        break

il_cands_path = ROOT / "il" / "candidates.json"
if not il_cands_path.exists():
    errors.append("missing public/data/il/candidates.json")
else:
    il_cands = json.loads(il_cands_path.read_text())
    if not isinstance(il_cands, list) or len(il_cands) != 528:
        errors.append(f"IL candidates.json rows {len(il_cands) if isinstance(il_cands, list) else type(il_cands)} != 528")
    else:
        if {r.get("list_kind") for r in il_cands} != {"latest_filed_rss"}:
            errors.append("IL list_kind must be latest_filed_rss")
        keys = {r.get("contest_key") for r in il_cands}
        if not (300 <= len(keys) <= 420):
            errors.append(f"IL contest_key_count {len(keys)} not ~339")
        if any(r.get("retrieved_at") != "2026-09-02T12:56:30Z" for r in il_cands):
            errors.append("IL candidates retrieved_at must be 2026-09-02T12:56:30Z")
        if any(r.get("certified") is not False for r in il_cands):
            errors.append("IL candidates must be labeled not certified")
        if any(not str(r.get("contest_key") or "").startswith("IL|") or str(r.get("contest_key") or "").count("|") != 3 for r in il_cands):
            errors.append("IL contest_key must be IL|OFFICE|DIST|")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in il_cands):
            errors.append("IL candidates must not use Ballotpedia")
        if any("elections.il.gov/RSS/LatestCandidatesFiled" not in (r.get("source_url") or "") for r in il_cands):
            errors.append("IL candidates source_url must be official SBE RSS")
        if not any(r.get("candidate_name") == "Jared Ploger" for r in il_cands):
            errors.append("IL RSS missing filed name Jared Ploger")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in il_cands):
            errors.append("IL candidates must omit streets/email/phone")
il_fec_path = ROOT / "il" / "fec-donors.json"
if not il_fec_path.exists():
    errors.append("missing public/data/il/fec-donors.json")
else:
    ilfec = json.loads(il_fec_path.read_text())
    if ilfec.get("row_count") != 48312 or ilfec.get("candidate_count") != 189:
        errors.append(f"IL FEC {ilfec.get('row_count')}/{ilfec.get('candidate_count')} != 48312/189")
    if not ilfec.get("do_not_sell_donor_lists") or not ilfec.get("streets_omitted"):
        errors.append("IL FEC extract must omit streets and say do_not_sell_donor_lists")
    if any("ballotpedia" in u.lower() or "open.fec.gov" in u.lower() for u in _urls(ilfec)):
        errors.append("IL FEC extract must not use Ballotpedia or OpenFEC")
_check_votes(ROOT / "il" / "votes.json", "IL", 740, {"D000622", "D000563"})
if (ROOT / "il" / "legislature-vote-index.json").exists():
    il_idx = json.loads((ROOT / "il" / "legislature-vote-index.json").read_text())
    if il_idx.get("kind") != "legislature_vote_index":
        errors.append("IL legislature-vote-index must be URL index only")
    if not any("ilga.gov" in (s.get("url") or "") for s in il_idx.get("sources") or []):
        errors.append("IL legislature index must cite official ilga.gov")
    if any("ballotpedia" in (s.get("url") or "").lower() for s in il_idx.get("sources") or []):
        errors.append("IL legislature index must not use Ballotpedia")

# Florida DOS extracts + Clerk/LIS + federal FEC (state donors blocked)
fl_stub_path = ROOT / "fl.json"
fl_cands_path = ROOT / "fl" / "candidates.json"
fl_votes_path = ROOT / "fl" / "votes.json"
fl_fec_path = ROOT / "fl" / "fec-donors.json"
if not fl_stub_path.exists():
    errors.append("missing public/data/fl.json")
else:
    flj = json.loads(fl_stub_path.read_text())
    donors_block = ((flj.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") != "partial" or donors_block.get("path") != "/data/fl/fec-donors.json":
        errors.append("fl.json donors must be federal FEC partial (state bulk blocked)")
    if not donors_block.get("do_not_sell_donor_lists"):
        errors.append("fl.json donors must say do_not_sell_donor_lists")
    scope = (donors_block.get("scope") or "").lower()
    if "fec" not in scope or "form-limited" not in scope:
        errors.append("fl.json donors.scope must say federal FEC and state form-limited")
    if flj.get("candidates_path") != "/data/fl/candidates.json" or flj.get("votes_path") != "/data/fl/votes.json":
        errors.append("fl.json candidates_path/votes_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(flj)):
        errors.append("fl.json must not use Ballotpedia")
    if flj.get("election", {}).get("state_code") != "FL":
        errors.append("fl.json election must be Florida / FL")
if not fl_cands_path.exists():
    errors.append("missing public/data/fl/candidates.json")
else:
    fl_cands = json.loads(fl_cands_path.read_text())
    if not isinstance(fl_cands, list) or len(fl_cands) != 3801:
        errors.append(f"FL candidates.json rows {len(fl_cands) if isinstance(fl_cands, list) else type(fl_cands)} != 3801")
    else:
        kinds = Counter(r.get("list_kind") for r in fl_cands)
        if kinds.get("state_extract") != 1145 or kinds.get("local_extract") != 2656:
            errors.append(f"FL list_kind split {dict(kinds)} != 1145/2656")
        if any(not str(r.get("contest_key") or "").startswith("FL|") or str(r.get("contest_key") or "").count("|") != 3 for r in fl_cands):
            errors.append("FL contest_key must be FL|OFFICE|DIST|")
        if not any(r.get("candidate_name") == "Byron Donalds" and r.get("office") == "Governor" for r in fl_cands):
            errors.append("FL list missing filed name Byron Donalds")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone", "voterid"}
        if any(street_keys & {k.lower() for k in r} for r in fl_cands):
            errors.append("FL candidates must omit streets/email/phone")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in fl_cands):
            errors.append("FL candidates must not use Ballotpedia")
if fl_fec_path.exists():
    flfec = json.loads(fl_fec_path.read_text())
    if flfec.get("row_count") != 55918 or flfec.get("candidate_count") != 339:
        errors.append(f"FL FEC {flfec.get('row_count')}/{flfec.get('candidate_count')} != 55918/339")
_check_votes(fl_votes_path, "FL", 1140, {"S001217", "M001244", "W000797"})
if (ROOT / "fl" / "congress-delegation.json").exists():
    fl_del = json.loads((ROOT / "fl" / "congress-delegation.json").read_text())
    if not any(v.get("district") == "FL-20" for v in fl_del.get("vacant") or []):
        errors.append("FL congress-delegation must flag vacant FL-20")
if any((v.get("district") or "") == "FL-20" for v in (json.loads(fl_votes_path.read_text()).get("votes") or []) if fl_votes_path.exists()):
    errors.append("FL-20 vacant seat must be skipped")

# Michigan MiTN + BOE listings + votes + FEC
mi_path = ROOT / "mi" / "mitn-donors.json"
mi_stub = ROOT / "mi.json"
if not mi_path.exists() or not mi_stub.exists():
    errors.append("MI extract missing public/data/mi/mitn-donors.json or public/data/mi.json")
else:
    mi = json.loads(mi_path.read_text())
    mi_json = json.loads(mi_stub.read_text())
    donors_block = ((mi_json.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") != "sourced" or donors_block.get("path") != "/data/mi/mitn-donors.json":
        errors.append("mi.json donors must stay sourced at /data/mi/mitn-donors.json")
    if donors_block.get("counts", {}).get("rows") != 964108:
        errors.append(f"mi.json donor counts {donors_block.get('counts')}")
    if mi.get("row_count") != 964108:
        errors.append(f"MI row_count {mi.get('row_count')} != 964108")
    if mi_json.get("candidates_path") != "/data/mi/candidates.json" or mi_json.get("votes_path") != "/data/mi/votes.json":
        errors.append("mi.json candidates_path/votes_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(mi_json)):
        errors.append("mi.json must not use Ballotpedia")
mi_cands_path = ROOT / "mi" / "candidates.json"
if not mi_cands_path.exists():
    errors.append("missing public/data/mi/candidates.json")
else:
    mi_cands = json.loads(mi_cands_path.read_text())
    if not isinstance(mi_cands, list) or len(mi_cands) != 1326:
        errors.append(f"MI candidates.json rows {len(mi_cands) if isinstance(mi_cands, list) else type(mi_cands)} != 1326")
    else:
        pri = [r for r in mi_cands if r.get("list_kind") == "primary_official_listing"]
        gen = [r for r in mi_cands if r.get("list_kind") == "general_unofficial_listing"]
        if len(pri) != 611 or len(gen) != 715:
            errors.append(f"MI pri/gen split {len(pri)}/{len(gen)} != 611/715")
        if not any("Benson" in (r.get("candidate_name") or "") for r in mi_cands):
            errors.append("MI list missing filed name Benson")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in mi_cands):
            errors.append("MI candidates must not use Ballotpedia")
if (ROOT / "mi" / "candidate-summary.json").exists():
    mi_sum = json.loads((ROOT / "mi" / "candidate-summary.json").read_text())
    if mi_sum.get("complete") is not False or mi_sum.get("general_unofficial_listing_rows") != 715:
        errors.append("MI candidate-summary must label general 715/720 complete=false")
_check_votes(ROOT / "mi" / "votes.json", "MI", 580, {"P000595", "S001208"})
if (ROOT / "mi" / "fec-donors.json").exists():
    mifec = json.loads((ROOT / "mi" / "fec-donors.json").read_text())
    if mifec.get("row_count") != 54868 or mifec.get("candidate_count") != 127:
        errors.append(f"MI FEC {mifec.get('row_count')}/{mifec.get('candidate_count')} != 54868/127")

# New York: Who Filed 1685 (1338 pri + 347 gen / 175 keys) + votes + FEC + NYSBOE
ny_stub_path = ROOT / "ny.json"
if not ny_stub_path.exists():
    errors.append("missing public/data/ny.json")
else:
    nyj = json.loads(ny_stub_path.read_text())
    if nyj.get("candidates_path") != "/data/ny/candidates.json":
        errors.append("ny.json candidates_path missing")
    if nyj.get("votes_path") != "/data/ny/votes.json":
        errors.append("ny.json votes_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(nyj)):
        errors.append("ny.json must not use Ballotpedia")
    cand_block = ((nyj.get("state_filings") or {}).get("candidates") or {})
    if cand_block.get("status") != "partial" or cand_block.get("complete") is not False:
        errors.append("ny.json candidates must be partial complete=false")
    if cand_block.get("path") != "/data/ny/candidates.json":
        errors.append("ny.json candidates.path missing")
    counts = cand_block.get("counts") or {}
    if counts.get("rows") != 1685 or counts.get("primary") != 1338 or counts.get("general") != 347 or counts.get("contest_keys") != 175:
        errors.append(f"ny.json Who Filed counts {counts}")
ny_cands_path = ROOT / "ny" / "candidates.json"
if not ny_cands_path.exists():
    errors.append("missing public/data/ny/candidates.json")
else:
    ny_cands = json.loads(ny_cands_path.read_text())
    if not isinstance(ny_cands, list) or len(ny_cands) != 1685:
        errors.append(f"NY candidates.json rows {len(ny_cands) if isinstance(ny_cands, list) else type(ny_cands)} != 1685")
    else:
        kinds = Counter(r.get("list_kind") for r in ny_cands)
        if kinds.get("who_filed_primary") != 1338 or kinds.get("who_filed_general") != 347:
            errors.append(f"NY list_kind split {dict(kinds)} != 1338/347")
        keys = {r.get("contest_key") for r in ny_cands}
        if len(keys) != 175:
            errors.append(f"NY contest_keys {len(keys)} != 175")
        if any(not str(r.get("contest_key") or "").startswith("NY|") or str(r.get("contest_key") or "").count("|") != 3 for r in ny_cands):
            errors.append("NY contest_key must be NY|OFFICE|DIST|DIST2")
        if any(r.get("complete") is not False for r in ny_cands):
            errors.append("NY candidates must be labeled complete=false")
        if any(r.get("retrieved_at") != "2026-09-02T17:06:00Z" for r in ny_cands):
            errors.append("NY candidates retrieved_at must be 2026-09-02T17:06:00Z")
        if any("publicreporting.elections.ny.gov/WhoFiled" not in (r.get("source_url") or "") for r in ny_cands):
            errors.append("NY candidates source_url must be official NYSBOE Who Filed")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in ny_cands):
            errors.append("NY candidates must not use Ballotpedia")
        if not any(r.get("candidate_name") == "Kathy C. Hochul" for r in ny_cands):
            errors.append("NY list missing filed name Kathy C. Hochul")
        if not any(r.get("candidate_name") == "George S. Latimer" for r in ny_cands):
            errors.append("NY list missing filed name George S. Latimer")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in ny_cands):
            errors.append("NY candidates must omit streets/email/phone")
if (ROOT / "ny" / "candidate-summary.json").exists():
    ny_sum = json.loads((ROOT / "ny" / "candidate-summary.json").read_text())
    if ny_sum.get("row_count") != 1685 or ny_sum.get("contest_key_count") != 175 or ny_sum.get("complete") is not False:
        errors.append(f"NY candidate-summary {ny_sum}")
else:
    errors.append("missing public/data/ny/candidate-summary.json")
_check_votes(ROOT / "ny" / "votes.json", "NY", 1100, {"S000148", "G000555"})
if (ROOT / "ny" / "fec-donors.json").exists():
    nyfec = json.loads((ROOT / "ny" / "fec-donors.json").read_text())
    if nyfec.get("row_count") != 68908 or nyfec.get("candidate_count") != 202:
        errors.append(f"NY FEC {nyfec.get('row_count')}/{nyfec.get('candidate_count')} != 68908/202")
if not (ROOT / "ny" / "nysboe-donors.json").exists():
    errors.append("missing public/data/ny/nysboe-donors.json")
else:
    nyd = json.loads((ROOT / "ny" / "nysboe-donors.json").read_text())
    if (nyd.get("row_count") or 0) < 680000:
        errors.append(f"NY NYSBOE row_count {nyd.get('row_count')} too low")
    if not nyd.get("do_not_sell_donor_lists") or not nyd.get("streets_omitted"):
        errors.append("NY NYSBOE extract must omit streets and say do_not_sell_donor_lists")
    if "e9ss-239a" not in (nyd.get("source_url") or ""):
        errors.append("nysboe-donors.json source_url must be official Open NY e9ss-239a")
    nyj = json.loads((ROOT / "ny.json").read_text())
    if ((nyj.get("state_filings") or {}).get("donors") or {}).get("path") != "/data/ny/nysboe-donors.json":
        errors.append("ny.json donors.path must be /data/ny/nysboe-donors.json")
    if ((nyj.get("state_filings") or {}).get("federal_fec") or {}).get("path") != "/data/ny/fec-donors.json":
        errors.append("ny.json federal_fec.path must stay /data/ny/fec-donors.json")

# Texas SOS cert + TEC + votes + FEC
tx_stub_path = ROOT / "tx.json"
tx_cands_path = ROOT / "tx" / "candidates.json"
if not tx_stub_path.exists():
    errors.append("missing public/data/tx.json")
else:
    txj = json.loads(tx_stub_path.read_text())
    if txj.get("candidates_path") != "/data/tx/candidates.json" or txj.get("votes_path") != "/data/tx/votes.json":
        errors.append("tx.json candidates_path/votes_path missing")
    donors_block = ((txj.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") != "sourced" or donors_block.get("path") != "/data/tx/tec-donors.json":
        errors.append("tx.json donors must stay sourced at /data/tx/tec-donors.json")
    if ((txj.get("state_filings") or {}).get("federal_fec") or {}).get("path") != "/data/tx/fec-donors.json":
        errors.append("tx.json federal_fec.path must stay /data/tx/fec-donors.json")
    if any("ballotpedia" in u.lower() for u in _urls(txj)):
        errors.append("tx.json must not use Ballotpedia")
if not tx_cands_path.exists():
    errors.append("missing public/data/tx/candidates.json")
else:
    tx_cands = json.loads(tx_cands_path.read_text())
    if not isinstance(tx_cands, list) or len(tx_cands) != 3823:
        errors.append(f"TX candidates.json rows {len(tx_cands) if isinstance(tx_cands, list) else type(tx_cands)} != 3823")
    else:
        if {r.get("list_kind") for r in tx_cands} != {"general_ballot_certification"}:
            errors.append("TX list_kind must be general_ballot_certification")
        keys = {r.get("contest_key") for r in tx_cands}
        if not (3000 <= len(keys) <= 3200):
            errors.append(f"TX contest_key_count {len(keys)} not ~3050")
        if any(not str(r.get("contest_key") or "").startswith("TX|") or str(r.get("contest_key") or "").count("|") != 3 for r in tx_cands):
            errors.append("TX contest_key must be TX|OFFICE|DIST|")
        if any(r.get("retrieved_at") != "2026-09-02T12:56:00Z" for r in tx_cands):
            errors.append("TX candidates retrieved_at must be 2026-09-02T12:56:00Z")
        if any(r.get("certification_date") != "2026-08-28" for r in tx_cands):
            errors.append("TX certification_date must be 2026-08-28")
        if not any(r.get("candidate_name") == "GREG ABBOTT" for r in tx_cands):
            errors.append("TX cert missing filed name GREG ABBOTT")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in tx_cands):
            errors.append("TX candidates must not use Ballotpedia")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in tx_cands):
            errors.append("TX candidates must omit streets/email/phone")
_check_votes(ROOT / "tx" / "votes.json", "TX", 1540, {"C001056", "C001098"})
if (ROOT / "tx" / "congress-delegation.json").exists():
    tx_del = json.loads((ROOT / "tx" / "congress-delegation.json").read_text())
    if not any(v.get("district") == "TX-23" for v in tx_del.get("vacant") or []):
        errors.append("TX congress-delegation must flag vacant TX-23")
if (ROOT / "tx" / "fec-donors.json").exists():
    txfec = json.loads((ROOT / "tx" / "fec-donors.json").read_text())
    if txfec.get("row_count") != 83868 or txfec.get("candidate_count") != 389:
        errors.append(f"TX FEC {txfec.get('row_count')}/{txfec.get('candidate_count')} != 83868/389")
if (ROOT / "tx" / "tec-donors.json").exists():
    tec = json.loads((ROOT / "tx" / "tec-donors.json").read_text())
    if (tec.get("row_count") or 0) < 3_000_000:
        errors.append(f"TX TEC row_count {tec.get('row_count')} too low")
    if not tec.get("do_not_sell_donor_lists") or not tec.get("streets_omitted"):
        errors.append("TX TEC extract must omit streets and say do_not_sell_donor_lists")

# Wave-3: FEC + Clerk/LIS votes for PA/OH/GA/NJ/NC. Ballots: NC 4256, NJ 97 federal_only, OH package 20 if present, PA/GA none.
WAVE3_RETRIEVED = "2026-09-02T15:58:08Z"
WAVE3_FEC = {
    "PA": {"kept": 30261, "cands": 114, "with": 59, "empty": 55, "votes": 740, "bios": {"F000466", "B001296"}},
    "OH": {"kept": 37133, "cands": 112, "with": 67, "empty": 45, "votes": 660, "bios": {"L000601", "T000490"}},
    "GA": {"kept": 52119, "cands": 172, "with": 100, "empty": 72, "votes": 587, "bios": {"C001103", "B001328"}},
    "NJ": {"kept": 32926, "cands": 127, "with": 80, "empty": 47, "votes": 540, "bios": {"N000188", "V000133"}},
}
WAVE3_NAMES = {
    "PA": "Pennsylvania",
    "OH": "Ohio",
    "GA": "Georgia",
    "NJ": "New Jersey",
}
for st, exp in WAVE3_FEC.items():
    sl = st.lower()
    stub_path = ROOT / f"{sl}.json"
    fec_path = ROOT / sl / "fec-donors.json"
    votes_path = ROOT / sl / "votes.json"
    if not stub_path.exists():
        errors.append(f"missing public/data/{sl}.json")
        continue
    stub = json.loads(stub_path.read_text())
    if stub.get("votes_path") != f"/data/{sl}/votes.json":
        errors.append(f"{st} votes_path missing")
    if stub.get("election", {}).get("state_code") != st or stub.get("election", {}).get("jurisdiction") != WAVE3_NAMES[st]:
        errors.append(f"{st} election must be {WAVE3_NAMES[st]} / {st}")
    if any("ballotpedia" in u.lower() for u in _urls(stub)):
        errors.append(f"{st} stub must not use Ballotpedia")
    fec_block = ((stub.get("state_filings") or {}).get("federal_fec") or {}) if st == "PA" else ((stub.get("state_filings") or {}).get("donors") or {})
    if st == "PA":
        donors_block = ((stub.get("state_filings") or {}).get("donors") or {})
        if donors_block.get("status") != "sourced" or donors_block.get("path") != "/data/pa/dos-donors.json":
            errors.append("pa.json donors must be sourced at /data/pa/dos-donors.json")
        if donors_block.get("counts", {}).get("rows") != 375604 or donors_block.get("counts", {}).get("filers") != 1239:
            errors.append(f"pa.json DOS donor counts {donors_block.get('counts')}")
        if donors_block.get("retrieved_at") != "2026-09-02T16:08:35Z":
            errors.append("pa.json DOS retrieved_at must be 2026-09-02T16:08:35Z")
        if not donors_block.get("do_not_sell_donor_lists"):
            errors.append("pa.json donors must say do_not_sell_donor_lists")
        if fec_block.get("status") != "partial" or fec_block.get("path") != "/data/pa/fec-donors.json":
            errors.append("pa.json federal_fec must stay partial at /data/pa/fec-donors.json")
        if stub.get("candidates_path") or (ROOT / "pa" / "candidates.json").exists():
            errors.append("PA must not ship candidates until official ballots clear")
    else:
        donors_block = ((stub.get("state_filings") or {}).get("donors") or {})
        if donors_block.get("status") != "partial" or donors_block.get("path") != f"/data/{sl}/fec-donors.json":
            errors.append(f"{st} donors must stay federal FEC partial at /data/{sl}/fec-donors.json")
        counts = donors_block.get("counts") or {}
        if counts.get("candidates") != exp["cands"] or counts.get("kept_rows") != exp["kept"]:
            errors.append(f"{st} donor counts {counts} != {exp['cands']} / {exp['kept']}")
        if donors_block.get("retrieved_at") != WAVE3_RETRIEVED:
            errors.append(f"{st} donors.retrieved_at must be {WAVE3_RETRIEVED}")
        if not donors_block.get("do_not_sell_donor_lists"):
            errors.append(f"{st} donors must say do_not_sell_donor_lists")
    if not fec_path.exists():
        errors.append(f"missing public/data/{sl}/fec-donors.json")
    else:
        fec = json.loads(fec_path.read_text())
        if fec.get("source_url") != "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip":
            errors.append(f"{st} FEC source_url must be official indiv26.zip")
        if fec.get("fec_api_key_present"):
            errors.append(f"{st} FEC must not use OpenFEC/DEMO_KEY")
        if fec.get("row_count") != exp["kept"] or fec.get("candidate_count") != exp["cands"]:
            errors.append(f"{st} FEC {fec.get('row_count')}/{fec.get('candidate_count')} != {exp['kept']}/{exp['cands']}")
        with_n = sum(1 for v in (fec.get("by_candidate") or {}).values() if (v.get("item_count_all") or 0) > 0)
        empty_n = sum(1 for v in (fec.get("by_candidate") or {}).values() if (v.get("item_count_all") or 0) == 0)
        if with_n != exp["with"] or empty_n != exp["empty"]:
            errors.append(f"{st} FEC with/empty {with_n}/{empty_n} != {exp['with']}/{exp['empty']}")
        if not fec.get("do_not_sell_donor_lists") or not fec.get("streets_omitted"):
            errors.append(f"{st} FEC extract must omit streets and say do_not_sell_donor_lists")
        if fec.get("retrieved_at") != WAVE3_RETRIEVED:
            errors.append(f"{st} FEC retrieved_at must be {WAVE3_RETRIEVED}")
        if any("ballotpedia" in u.lower() or "open.fec.gov" in u.lower() for u in _urls(fec)):
            errors.append(f"{st} FEC extract must not use Ballotpedia or OpenFEC")
        street = {"street", "address", "addr", "zip", "zipcode", "contributor_zip"}
        for rec in (fec.get("by_candidate") or {}).values():
            for it in rec.get("items") or []:
                if street & {k.lower() for k in it}:
                    errors.append(f"{st} FEC item has a street-address or zip field")
                    break
            else:
                continue
            break
    _check_votes(votes_path, st, exp["votes"], exp["bios"])
    if votes_path.exists():
        payload = json.loads(votes_path.read_text())
        if payload.get("retrieved_at") != WAVE3_RETRIEVED:
            errors.append(f"{st} votes retrieved_at must be {WAVE3_RETRIEVED}")
    if st == "GA":
        if stub.get("candidates_path") or (ROOT / "ga" / "candidates.json").exists():
            errors.append("GA must not ship candidates until official ballots clear")
        if votes_path.exists():
            payload = json.loads(votes_path.read_text())
            if (payload.get("counts_by_member") or {}).get("B001328") != 7:
                errors.append("GA-13 Blair must keep official 7 Clerk rolls (sworn 2026-09-01); do not invent earlier votes")

# Pennsylvania DOS 2026 Full Export (never wipe FEC)
pa_dos = ROOT / "pa" / "dos-donors.json"
if not pa_dos.exists():
    errors.append("missing public/data/pa/dos-donors.json")
else:
    pad = json.loads(pa_dos.read_text())
    if pad.get("row_count") != 375604 or pad.get("filer_count") != 1239:
        errors.append(f"PA DOS {pad.get('row_count')}/{pad.get('filer_count')} != 375604/1239")
    if pad.get("retrieved_at") != "2026-09-02T16:08:35Z":
        errors.append("PA DOS retrieved_at must be 2026-09-02T16:08:35Z")
    if "2026.zip" not in (pad.get("source_url") or ""):
        errors.append("PA DOS source_url must be official 2026.zip")
    if not pad.get("do_not_sell_donor_lists") or not pad.get("streets_omitted"):
        errors.append("PA DOS extract must omit streets and say do_not_sell_donor_lists")
    if any("ballotpedia" in u.lower() for u in _urls(pad)):
        errors.append("PA DOS extract must not use Ballotpedia")
    street = {"street", "address", "addr", "zip", "zipcode", "contributor_zip"}
    for rec in (pad.get("by_candidate") or {}).values():
        for it in rec.get("items") or []:
            if street & {k.lower() for k in it}:
                errors.append("PA DOS item has a street-address or zip field")
                break
        else:
            continue
        break

# New Jersey official federal candidate PDFs (primary 57 + general 40 = 97)
nj_cands_path = ROOT / "nj" / "candidates.json"
if not nj_cands_path.exists():
    errors.append("missing public/data/nj/candidates.json")
else:
    nj_cands = json.loads(nj_cands_path.read_text())
    if not isinstance(nj_cands, list) or len(nj_cands) != 97:
        errors.append(f"NJ candidates.json rows {len(nj_cands) if isinstance(nj_cands, list) else type(nj_cands)} != 97")
    else:
        kinds = Counter(r.get("list_kind") for r in nj_cands)
        if kinds.get("official_primary") != 57 or kinds.get("official_general") != 40:
            errors.append(f"NJ list_kind split {dict(kinds)} != 57/40")
        if any(r.get("federal_only") is not True for r in nj_cands):
            errors.append("NJ candidates must be labeled federal_only")
        if any(not str(r.get("contest_key") or "").startswith("NJ|") or str(r.get("contest_key") or "").count("|") != 3 for r in nj_cands):
            errors.append("NJ contest_key must be NJ|OFFICE|DIST|")
        if any(r.get("complete") is not False for r in nj_cands):
            errors.append("NJ candidates must be labeled complete=false")
        if any(r.get("retrieved_at") != "2026-09-02T16:10:00Z" for r in nj_cands):
            errors.append("NJ candidates retrieved_at must be 2026-09-02T16:10:00Z")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in nj_cands):
            errors.append("NJ candidates must not use Ballotpedia")
        if any("nj.gov/state/elections" not in (r.get("source_url") or "") for r in nj_cands):
            errors.append("NJ candidates source_url must be official nj.gov elections PDFs")
        if not any(r.get("candidate_name") == "CORY BOOKER" and r.get("office") == "U.S. Senate" for r in nj_cands):
            errors.append("NJ list missing filed name CORY BOOKER")
        if not any(r.get("candidate_name") == "DONALD NORCROSS" for r in nj_cands):
            errors.append("NJ list missing filed name DONALD NORCROSS")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in nj_cands):
            errors.append("NJ candidates must omit streets/email/phone")
nj_stub = json.loads((ROOT / "nj.json").read_text()) if (ROOT / "nj.json").exists() else {}
if nj_stub.get("candidates_path") != "/data/nj/candidates.json":
    errors.append("nj.json candidates_path missing")

# Ohio: 20 Dir 2026-45 statewide (complete=false) + votes + FEC. No US House. No 31-row dump.
oh_cands_path = ROOT / "oh" / "candidates.json"
oh_stub = json.loads((ROOT / "oh.json").read_text()) if (ROOT / "oh.json").exists() else {}
if not (oh_stub.get("election") or {}).get("ballots_incomplete"):
    errors.append("oh.json must label ballots incomplete")
if oh_stub.get("candidates_path") != "/data/oh/candidates.json":
    errors.append("oh.json candidates_path missing")
if not oh_cands_path.exists():
    errors.append("missing public/data/oh/candidates.json")
else:
    oh_cands = json.loads(oh_cands_path.read_text())
    if not isinstance(oh_cands, list) or len(oh_cands) != 20:
        errors.append(f"OH candidates.json rows {len(oh_cands) if isinstance(oh_cands, list) else type(oh_cands)} != 20 Dir 2026-45 statewide")
    else:
        if {r.get("list_kind") for r in oh_cands} != {"dir_2026_45"}:
            errors.append("OH list_kind must be dir_2026_45")
        if any(r.get("complete") is not False for r in oh_cands):
            errors.append("OH candidates must be labeled complete=false")
        if any(r.get("directive") != "2026-45" for r in oh_cands):
            errors.append("OH candidates must be labeled directive 2026-45")
        if any(r.get("retrieved_at") != "2026-09-02T16:45:00Z" for r in oh_cands):
            errors.append("OH candidates retrieved_at must be 2026-09-02T16:45:00Z")
        if any((r.get("office") or "").lower().startswith("u.s. house") or (r.get("office") or "").lower().startswith("us house") for r in oh_cands):
            errors.append("OH package must not invent US House rows")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in oh_cands):
            errors.append("OH candidates must not use Ballotpedia")
        if not any(r.get("candidate_name") == "Sherrod Brown" and r.get("office") == "U.S. Senate" for r in oh_cands):
            errors.append("OH list missing filed name Sherrod Brown")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in oh_cands):
            errors.append("OH candidates must omit streets/email/phone")
if (ROOT / "oh" / "candidate-summary.json").exists():
    oh_sum = json.loads((ROOT / "oh" / "candidate-summary.json").read_text())
    if oh_sum.get("row_count") != 20 or oh_sum.get("complete") is not False:
        errors.append(f"OH candidate-summary {oh_sum}")
else:
    errors.append("missing public/data/oh/candidate-summary.json")

nc_stub_path = ROOT / "nc.json"
nc_cands_path = ROOT / "nc" / "candidates.json"
nc_fec_path = ROOT / "nc" / "fec-donors.json"
if not nc_stub_path.exists():
    errors.append("missing public/data/nc.json")
else:
    ncj = json.loads(nc_stub_path.read_text())
    if ncj.get("candidates_path") != "/data/nc/candidates.json" or ncj.get("votes_path") != "/data/nc/votes.json":
        errors.append("nc.json candidates_path/votes_path missing")
    donors_block = ((ncj.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") != "partial" or donors_block.get("path") != "/data/nc/fec-donors.json":
        errors.append("nc.json donors must stay federal FEC partial at /data/nc/fec-donors.json")
    counts = donors_block.get("counts") or {}
    if counts.get("candidates") != 130 or counts.get("kept_rows") != 29603:
        errors.append(f"nc.json donor counts {counts} != 130 / 29603")
    if donors_block.get("retrieved_at") != WAVE3_RETRIEVED:
        errors.append("nc.json donors.retrieved_at must be 2026-09-02T15:58:08Z")
    if ncj.get("election", {}).get("state_code") != "NC" or ncj.get("election", {}).get("jurisdiction") != "North Carolina":
        errors.append("nc.json election must be North Carolina / NC")
    if any("ballotpedia" in u.lower() for u in _urls(ncj)):
        errors.append("nc.json must not use Ballotpedia")
if not nc_cands_path.exists():
    errors.append("missing public/data/nc/candidates.json")
else:
    nc_cands = json.loads(nc_cands_path.read_text())
    if not isinstance(nc_cands, list) or len(nc_cands) != 4256:
        errors.append(f"NC candidates.json rows {len(nc_cands) if isinstance(nc_cands, list) else type(nc_cands)} != 4256")
    else:
        kinds = Counter(r.get("list_kind") for r in nc_cands)
        if kinds.get("ncsbe_general") != 2789 or kinds.get("ncsbe_primary") != 1467:
            errors.append(f"NC list_kind split {dict(kinds)} != 2789/1467")
        keys = {r.get("contest_key") for r in nc_cands}
        if len(keys) != 1377:
            errors.append(f"NC contest_keys {len(keys)} != 1377")
        if any(not str(r.get("contest_key") or "").startswith("NC|") or str(r.get("contest_key") or "").count("|") != 3 for r in nc_cands):
            errors.append("NC contest_key must be NC|OFFICE|DIST|")
        if any(r.get("retrieved_at") != "2026-09-02T16:05:00Z" for r in nc_cands):
            errors.append("NC candidates retrieved_at must be 2026-09-02T16:05:00Z")
        if any(r.get("complete") is not False for r in nc_cands):
            errors.append("NC candidates must be labeled complete=false")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in nc_cands):
            errors.append("NC candidates must not use Ballotpedia")
        if any("ncsbe.gov" not in (r.get("source_url") or "") and "dl.ncsbe.gov" not in (r.get("source_url") or "") for r in nc_cands):
            errors.append("NC candidates source_url must be official NCSBE CSV")
        if not any(r.get("candidate_name") == "Roy Cooper" and r.get("office") == "US SENATE" for r in nc_cands):
            errors.append("NC list missing filed name Roy Cooper")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in nc_cands):
            errors.append("NC candidates must omit streets/email/phone")
if (ROOT / "nc" / "candidate-summary.json").exists():
    nc_sum = json.loads((ROOT / "nc" / "candidate-summary.json").read_text())
    if nc_sum.get("row_count") != 4256 or nc_sum.get("contest_key_count") != 1377:
        errors.append(f"NC candidate-summary counts {nc_sum}")
    if nc_sum.get("complete") is not False or nc_sum.get("certified") is not False:
        errors.append("NC candidate-summary must be complete=false certified=false")
else:
    errors.append("missing public/data/nc/candidate-summary.json")
if not nc_fec_path.exists():
    errors.append("missing public/data/nc/fec-donors.json")
else:
    ncfec = json.loads(nc_fec_path.read_text())
    if ncfec.get("row_count") != 29603 or ncfec.get("candidate_count") != 130:
        errors.append(f"NC FEC {ncfec.get('row_count')}/{ncfec.get('candidate_count')} != 29603/130")
    if not ncfec.get("do_not_sell_donor_lists") or not ncfec.get("streets_omitted"):
        errors.append("NC FEC extract must omit streets and say do_not_sell_donor_lists")
    if ncfec.get("retrieved_at") != WAVE3_RETRIEVED:
        errors.append("NC FEC retrieved_at must be 2026-09-02T15:58:08Z")
    if any("ballotpedia" in u.lower() or "open.fec.gov" in u.lower() for u in _urls(ncfec)):
        errors.append("NC FEC extract must not use Ballotpedia or OpenFEC")
_check_votes(ROOT / "nc" / "votes.json", "NC", 620, {"D000230", "R000305"})
if (ROOT / "nc" / "votes.json").exists():
    ncv = json.loads((ROOT / "nc" / "votes.json").read_text())
    if ncv.get("retrieved_at") != WAVE3_RETRIEVED:
        errors.append("NC votes retrieved_at must be 2026-09-02T15:58:08Z")

# US Virgin Islands: official ESVI June 88 + August general 70 + FEC Delegate 8.
# Prefer August general for November. No US Senate. Streets omitted. Never wipe others.
vi_cands_path = ROOT / "vi" / "candidates.json"
vi_stub = json.loads((ROOT / "vi.json").read_text()) if (ROOT / "vi.json").exists() else {}
if not (ROOT / "vi.json").exists():
    errors.append("missing public/data/vi.json")
else:
    if vi_stub.get("candidates_path") != "/data/vi/candidates.json":
        errors.append("vi.json candidates_path missing")
    if vi_stub.get("election", {}).get("state_code") != "VI":
        errors.append("vi.json election.state_code must be VI")
    if vi_stub.get("election", {}).get("jurisdiction") != "U.S. Virgin Islands":
        errors.append("vi.json jurisdiction must be U.S. Virgin Islands")
    if vi_stub.get("election", {}).get("prefer_for_november") != "official_august":
        errors.append("vi.json must prefer official_august for November")
    if vi_stub.get("election", {}).get("no_us_senate") is not True:
        errors.append("vi.json must say no_us_senate")
    if vi_stub.get("election", {}).get("federal_offices") != ["Delegate to Congress"]:
        errors.append("vi.json federal_offices must be Delegate only")
    if vi_stub.get("election", {}).get("primary_certified") != "2026-08-25":
        errors.append("vi.json primary_certified must be 2026-08-25")
    if "2026-primary-election-certification" not in (vi_stub.get("election", {}).get("primary_certification_source") or ""):
        errors.append("vi.json must cite official VIVOTE Aug 25 primary certification")
    if vi_stub.get("votes_path") != "/data/vi/votes.json":
        errors.append("vi.json votes_path missing")
    if any("ballotpedia" in u.lower() for u in _urls(vi_stub)):
        errors.append("vi.json must not use Ballotpedia")
    cblock = ((vi_stub.get("state_filings") or {}).get("candidates") or {})
    if cblock.get("complete") is not True or cblock.get("retrieved_at") != "2026-09-03T13:54:09Z":
        errors.append("vi.json candidates block must be complete=true retrieved_at 2026-09-03T13:54:09Z")
    if (cblock.get("counts") or {}).get("rows") != 166:
        errors.append(f"vi.json candidate counts {cblock.get('counts')} != 166")
    donors_block = ((vi_stub.get("state_filings") or {}).get("donors") or {})
    if donors_block.get("status") != "partial" or donors_block.get("path") != "/data/vi/fec-donors.json":
        errors.append("vi.json donors must be federal FEC partial at /data/vi/fec-donors.json")
    dcounts = donors_block.get("counts") or {}
    if dcounts.get("candidates") != 9 or dcounts.get("with_receipts") != 4 or dcounts.get("kept_rows") != 326:
        errors.append(f"vi.json donor counts {dcounts} != 9/4/326")
    if donors_block.get("retrieved_at") != "2026-09-03T13:54:09Z":
        errors.append("vi.json donors.retrieved_at must be 2026-09-03T13:54:09Z")
    if donors_block.get("no_us_senate") is not True:
        errors.append("vi.json donors must say no_us_senate")
    state_donors = ((vi_stub.get("state_filings") or {}).get("state_donors") or {})
    if state_donors.get("status") != "pending":
        errors.append("vi.json territorial CF must stay pending")
    vblock = ((vi_stub.get("state_filings") or {}).get("votes") or {})
    if vblock.get("path") != "/data/vi/votes.json" or vblock.get("complete") is not False:
        errors.append("vi.json votes block must be complete=false at /data/vi/votes.json")
    if vblock.get("federal_only") is not True or vblock.get("no_us_senate") is not True:
        errors.append("vi.json votes must stay federal_only with no U.S. Senate")
    docs = vi_stub.get("docs") or {}
    if docs.get("source_meta") != "/data/vi/SOURCE_META.json":
        errors.append("vi.json docs.source_meta missing")
    if docs.get("notes") != "/data/vi/NOTES.md" or docs.get("schema") != "/data/vi/SCHEMA.md":
        errors.append("vi.json docs notes/schema missing")
    if docs.get("discovery") != "/data/vi/DISCOVERY.md":
        errors.append("vi.json docs.discovery missing")
if not vi_cands_path.exists():
    errors.append("missing public/data/vi/candidates.json")
else:
    vi_cands = json.loads(vi_cands_path.read_text())
    if not isinstance(vi_cands, list) or len(vi_cands) != 166:
        errors.append(f"VI candidates.json rows {len(vi_cands) if isinstance(vi_cands, list) else type(vi_cands)} != 166")
    else:
        kinds = Counter(r.get("list_kind") for r in vi_cands)
        if kinds.get("official_june") != 88 or kinds.get("official_august") != 70 or kinds.get("fec_delegate") != 8:
            errors.append(f"VI list_kind split {dict(kinds)} != 88/70/8")
        if any(r.get("complete") is not True for r in vi_cands):
            errors.append("VI candidates must be labeled complete=true")
        if any(r.get("retrieved_at") != "2026-09-03T13:54:09Z" for r in vi_cands):
            errors.append("VI candidates retrieved_at must be 2026-09-03T13:54:09Z")
        if any("senate" in (r.get("office") or "").lower() for r in vi_cands):
            errors.append("VI must not invent a U.S. Senate contest")
        if any(not str(r.get("contest_key") or "").startswith("VI|") or str(r.get("contest_key") or "").count("|") != 3 for r in vi_cands):
            errors.append("VI contest_key must be VI|OFFICE|DIST|")
        if any("ballotpedia" in (r.get("source_url") or "").lower() for r in vi_cands):
            errors.append("VI candidates must not use Ballotpedia")
        if any(
            "vivote.gov" not in (r.get("source_url") or "")
            and "fec.gov/files/bulk-downloads/2026/cn26.zip" not in (r.get("source_url") or "")
            for r in vi_cands
        ):
            errors.append("VI source_url must be official vivote.gov PDFs or FEC cn26")
        if not any(r.get("candidate_name") == "Janelle K. Sarauw" and r.get("list_kind") == "official_august" and r.get("office") == "Delegate to Congress" for r in vi_cands):
            errors.append("August general missing Janelle K. Sarauw Delegate")
        if not any(r.get("cand_id") == "H2VI00082" and r.get("list_kind") == "fec_delegate" for r in vi_cands):
            errors.append("FEC Delegate missing PLASKETT H2VI00082")
        street_keys = {"street", "address", "addr", "mailing_address", "email", "phone"}
        if any(street_keys & {k.lower() for k in r} for r in vi_cands):
            errors.append("VI candidates must omit streets/email/phone")
if (ROOT / "vi" / "candidate-summary.json").exists():
    vi_sum = json.loads((ROOT / "vi" / "candidate-summary.json").read_text())
    if vi_sum.get("row_count") != 166 or vi_sum.get("complete") is not True:
        errors.append(f"VI candidate-summary {vi_sum}")
    if vi_sum.get("prefer_for_november") != "official_august" or vi_sum.get("no_us_senate") is not True:
        errors.append("VI candidate-summary must prefer August general and omit Senate")
    if vi_sum.get("retrieved_at") != "2026-09-03T13:54:09Z":
        errors.append("VI candidate-summary retrieved_at must be 2026-09-03T13:54:09Z")
    if vi_sum.get("source_url") != "https://vivote.gov/?elections=2026-general-election":
        errors.append("VI candidate-summary source_url must stay official general landing")
    if vi_sum.get("primary_certified") != "2026-08-25":
        errors.append("VI candidate-summary primary_certified must be 2026-08-25")
    if vi_sum.get("june_17_is_primary_certification") is not False:
        errors.append("VI candidate-summary must mark june_17_is_primary_certification=false")
    if "june 17" in (vi_sum.get("note") or "").lower() and "not june 17" not in (vi_sum.get("note") or "").lower():
        errors.append("VI candidate-summary must not treat June 17 as primary certification")
    if not vi_sum.get("streets_omitted"):
        errors.append("VI candidate-summary must say streets_omitted")
else:
    errors.append("missing public/data/vi/candidate-summary.json")
vi_fec_path = ROOT / "vi" / "fec-donors.json"
if not vi_fec_path.exists():
    errors.append("missing public/data/vi/fec-donors.json")
else:
    vifec = json.loads(vi_fec_path.read_text())
    if vifec.get("row_count") != 326 or (vifec.get("counts") or {}).get("kept_rows") != 326:
        errors.append(f"VI FEC kept_rows {vifec.get('row_count')} != 326")
    if vifec.get("candidate_count") != 9 or (vifec.get("counts") or {}).get("with_receipts") != 4:
        errors.append(f"VI FEC candidates {vifec.get('candidate_count')}/{(vifec.get('counts') or {}).get('with_receipts')} != 9/4")
    if vifec.get("retrieved_at") != "2026-09-03T13:54:09Z":
        errors.append("VI FEC retrieved_at must be 2026-09-03T13:54:09Z")
    if vifec.get("source_url") != "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip":
        errors.append("vi/fec-donors.json source_url must be official indiv26.zip")
    if vifec.get("fec_api_key_present"):
        errors.append("vi/fec-donors.json must not use OpenFEC/DEMO_KEY")
    if not vifec.get("do_not_sell_donor_lists") or not vifec.get("streets_omitted"):
        errors.append("VI FEC extract must omit streets and say do_not_sell_donor_lists")
    if vifec.get("no_us_senate") is not True or vifec.get("no_us_senate_contest") is not True:
        errors.append("VI FEC extract must not present a Senate contest")
    if any("ballotpedia" in u.lower() or "open.fec.gov" in u.lower() for u in _urls(vifec)):
        errors.append("VI FEC extract must not use Ballotpedia or OpenFEC")
    byc = vifec.get("by_candidate") or {}
    if len(byc) != 9:
        errors.append(f"VI FEC by_candidate {len(byc)} != 9")
    senate = byc.get("S6VI00018") or {}
    if senate.get("status") != "empty" or senate.get("item_count_all") or senate.get("items"):
        errors.append("VI Senate as-filed row must stay honest-empty")
    if senate.get("not_a_contest") is not True or senate.get("office") != "S":
        errors.append("VI Senate as-filed row must be flagged not_a_contest")
    if not any(cid == "H2VI00082" and rec.get("status") == "ok" for cid, rec in byc.items()):
        errors.append("VI FEC missing PLASKETT receipts")
    street_keys = {"street", "address", "addr", "zip", "zipcode", "contributor_zip", "occupation"}
    for rec in byc.values():
        if street_keys & {k.lower() for k in rec}:
            errors.append("VI FEC candidate leaked a street/zip field")
        for item in rec.get("items") or []:
            if street_keys & {k.lower() for k in item}:
                errors.append("VI FEC item leaked a street/zip field")
            if not item.get("contributor_name") or item.get("amount") is None:
                errors.append("VI FEC item missing official contributor_name/amount")
vi_votes_path = ROOT / "vi" / "votes.json"
if not vi_votes_path.exists():
    errors.append("missing public/data/vi/votes.json")
else:
    vivotes = json.loads(vi_votes_path.read_text())
    if vivotes.get("complete") is not False or vivotes.get("federal_only") is not True:
        errors.append("VI votes.json must stay complete=false federal_only")
    if vivotes.get("no_us_senate") is not True or vivotes.get("no_us_senate_contest") is not True:
        errors.append("VI votes.json must not invent a U.S. Senate contest")
    if vivotes.get("office") != "Delegate to Congress":
        errors.append("VI votes.json office must stay Delegate to Congress")
    if vivotes.get("member_bioguide") != "P000610" or vivotes.get("district") != "VI-00":
        errors.append("VI votes.json member must stay official Clerk P000610 / VI-00")
    if vivotes.get("retrieved_at") != "2026-09-03T13:54:09Z":
        errors.append("VI votes.json retrieved_at must stay 2026-09-03T13:54:09Z")
    if vivotes.get("source_url") != "https://clerk.house.gov/evs/2026/index.asp":
        errors.append("VI votes.json source_url must stay official House Clerk EVS")
    if vivotes.get("count") != 19 or len(vivotes.get("votes") or []) != 19:
        errors.append(f"VI votes.json count {vivotes.get('count')} != 19 official recorded-votes")
    if (vivotes.get("counts_by_member") or {}) != {"P000610": 19}:
        errors.append("VI votes.json counts_by_member must stay P000610=19")
    if any((row.get("chamber") or "").lower() == "senate" for row in (vivotes.get("votes") or [])):
        errors.append("VI votes.json must not invent Senate rows")
    if any(row.get("bioguide_id") != "P000610" for row in (vivotes.get("votes") or [])):
        errors.append("VI votes.json rows must stay official Clerk bioguide P000610")
    if any(
        row.get("vote_cast") not in {"Yea", "Aye", "Nay", "No", "Present", "Not Voting"}
        or not row.get("source_url")
        or row.get("retrieved_at") != "2026-09-03T13:54:09Z"
        for row in (vivotes.get("votes") or [])
    ):
        errors.append("VI votes.json vote_cast/source_url/retrieved_at must stay official")
vi_meta_path = ROOT / "vi" / "SOURCE_META.json"
if not vi_meta_path.exists():
    errors.append("missing public/data/vi/SOURCE_META.json")
else:
    vimeta = json.loads(vi_meta_path.read_text())
    if vimeta.get("primary_certified") != "2026-08-25":
        errors.append("VI SOURCE_META primary_certified must be 2026-08-25")
    if vimeta.get("june_17_is_primary_certification") is not False:
        errors.append("VI SOURCE_META must mark june_17_is_primary_certification=false")
    if (vimeta.get("candidates") or {}).get("row_count") != 166:
        errors.append("VI SOURCE_META candidates.row_count must stay 166")
    if (vimeta.get("candidates") or {}).get("retrieved_at") != "2026-09-03T13:54:09Z":
        errors.append("VI SOURCE_META candidates.retrieved_at must stay intact")
    if (vimeta.get("fec_donors") or {}).get("kept_rows") != 326:
        errors.append("VI SOURCE_META fec_donors.kept_rows must stay 326")
    if (vimeta.get("votes") or {}).get("complete") is not False:
        errors.append("VI SOURCE_META votes must stay complete=false")
    if (vimeta.get("territorial_cf") or {}).get("status") != "pending":
        errors.append("VI SOURCE_META territorial CF must stay pending")
for name in ("NOTES.md", "SCHEMA.md", "DISCOVERY.md"):
    if not (ROOT / "vi" / name).is_file():
        errors.append(f"missing public/data/vi/{name}")

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
    "Kitashima",
    ((csc.get("by_candidate") or {}).get("KITASHIMA, Kelly Puamailani") or {}).get("status"),
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
    "OR FEC donors",
    json.loads((ROOT / "or" / "fec-donors.json").read_text()).get("row_count"),
    "AZ ballots",
    len(json.loads((ROOT / "az" / "candidates.json").read_text())),
    "AZ votes",
    json.loads((ROOT / "az" / "votes.json").read_text()).get("count"),
    "AZ FEC donors",
    json.loads((ROOT / "az" / "fec-donors.json").read_text()).get("candidate_count"),
)
if (ROOT / "mi" / "mitn-donors.json").exists():
    print(
        "OK MI MiTN rows",
        json.loads((ROOT / "mi" / "mitn-donors.json").read_text()).get("row_count"),
        "filers",
        json.loads((ROOT / "mi" / "mitn-donors.json").read_text()).get("filer_count"),
    )
if (ROOT / "il" / "sbe-donors.json").exists():
    print(
        "OK IL SBE rows",
        json.loads((ROOT / "il" / "sbe-donors.json").read_text()).get("row_count"),
        "filers",
        json.loads((ROOT / "il" / "sbe-donors.json").read_text()).get("filer_count"),
    )
if (ROOT / "il" / "candidates.json").exists():
    print(
        "OK IL ballots",
        len(json.loads((ROOT / "il" / "candidates.json").read_text())),
        "IL votes",
        json.loads((ROOT / "il" / "votes.json").read_text()).get("count"),
        "IL FEC",
        json.loads((ROOT / "il" / "fec-donors.json").read_text()).get("row_count"),
    )
if (ROOT / "fl" / "candidates.json").exists():
    print(
        "OK FL ballots",
        len(json.loads((ROOT / "fl" / "candidates.json").read_text())),
        "FL votes",
        json.loads((ROOT / "fl" / "votes.json").read_text()).get("count"),
        "FL FEC",
        json.loads((ROOT / "fl" / "fec-donors.json").read_text()).get("candidate_count"),
    )
if (ROOT / "mi" / "candidates.json").exists():
    print(
        "OK MI ballots",
        len(json.loads((ROOT / "mi" / "candidates.json").read_text())),
        "MI votes",
        json.loads((ROOT / "mi" / "votes.json").read_text()).get("count"),
    )
if (ROOT / "ny" / "votes.json").exists():
    print(
        "OK NY votes",
        json.loads((ROOT / "ny" / "votes.json").read_text()).get("count"),
        "NY FEC",
        json.loads((ROOT / "ny" / "fec-donors.json").read_text()).get("row_count"),
        "NY ballots",
        len(json.loads((ROOT / "ny" / "candidates.json").read_text())) if (ROOT / "ny" / "candidates.json").exists() else 0,
    )
if (ROOT / "tx" / "candidates.json").exists():
    print(
        "OK TX ballots",
        len(json.loads((ROOT / "tx" / "candidates.json").read_text())),
        "TX votes",
        json.loads((ROOT / "tx" / "votes.json").read_text()).get("count"),
        "TX TEC",
        json.loads((ROOT / "tx" / "tec-donors.json").read_text()).get("row_count"),
    )
if (ROOT / "nc" / "candidates.json").exists():
    print(
        "OK NC ballots",
        len(json.loads((ROOT / "nc" / "candidates.json").read_text())),
        "NC votes",
        json.loads((ROOT / "nc" / "votes.json").read_text()).get("count"),
        "NC FEC",
        json.loads((ROOT / "nc" / "fec-donors.json").read_text()).get("row_count"),
    )
if (ROOT / "vi" / "candidates.json").exists():
    print(
        "OK VI ballots",
        len(json.loads((ROOT / "vi" / "candidates.json").read_text())),
        "prefer",
        json.loads((ROOT / "vi.json").read_text()).get("election", {}).get("prefer_for_november"),
        "VI FEC",
        json.loads((ROOT / "vi" / "fec-donors.json").read_text()).get("row_count") if (ROOT / "vi" / "fec-donors.json").exists() else 0,
        "VI votes",
        json.loads((ROOT / "vi" / "votes.json").read_text()).get("count") if (ROOT / "vi" / "votes.json").exists() else 0,
        "primary",
        json.loads((ROOT / "vi.json").read_text()).get("election", {}).get("primary_certified"),
    )
for st in ("pa", "oh", "ga", "nj"):
    if (ROOT / st / "votes.json").exists() and (ROOT / st / "fec-donors.json").exists():
        extra = ""
        if (ROOT / st / "candidates.json").exists():
            extra = f" {st.upper()} ballots {len(json.loads((ROOT / st / 'candidates.json').read_text()))}"
        if st == "pa" and (ROOT / "pa" / "dos-donors.json").exists():
            extra += f" PA DOS {json.loads((ROOT / 'pa' / 'dos-donors.json').read_text()).get('row_count')}"
        print(
            f"OK {st.upper()} votes",
            json.loads((ROOT / st / "votes.json").read_text()).get("count"),
            f"{st.upper()} FEC",
            json.loads((ROOT / st / "fec-donors.json").read_text()).get("row_count"),
            extra,
        )
