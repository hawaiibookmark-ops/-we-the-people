#!/usr/bin/env python3
"""Build sourced civic data from official/primary public datasets only."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
CACHE = ROOT / ".cache"
FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}
STATE_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}
PARTY_NAME = {
    "D": "Democratic Party",
    "R": "Republican Party",
    "G": "Green Party",
    "L": "Libertarian Party",
    "N": "Nonpartisan",
    "NON": "Nonpartisan",
    "A": "Aloha Aina Party",
}
# USPS / Census county → island. Molokaʻi / Lānaʻi ZIPs from USPS ZIP list
# in Maui County (FIPS 15009).
MOLOKAI_ZIPS = {"96729", "96748", "96757", "96770"}
LANAI_ZIPS = {"96763"}
NIIHAU_ZIPS = {"96769"}  # Kekaha is Kauaʻi; Niʻihau shares rural Kauaʻi routing — flag if used
HI_COUNTY = {
    "15001": "Hawaiʻi County",
    "15003": "Honolulu County",
    "15007": "Kauaʻi County",
    "15009": "Maui County",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, timeout: int = 90) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^a-zA-Z0-9._-]+", "_", url)[-180:]
    path = CACHE / key
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {url}") from e
    path.write_bytes(data)
    return data


def fetch_text(url: str) -> str:
    raw = fetch(url)
    return raw.decode("utf-8-sig", errors="replace")


def source(url: str, retrieved_at: str, note: str = "") -> dict:
    item = {"url": url, "retrieved_at": retrieved_at}
    if note:
        item["note"] = note
    return item


def party_label(code: str) -> str:
    code = (code or "").strip()
    return PARTY_NAME.get(code, code or "Unspecified on source")


def parse_hi_summary(text: str) -> list[dict]:
    lines = text.splitlines()
    header = None
    rows = []
    for ln in lines:
        if ln.startswith("#Contest"):
            header = [h.strip() for h in ln.lstrip("#").split("\t")]
            continue
        if not ln.strip() or ln.startswith("#"):
            continue
        parts = ln.split("\t")
        if header is None or len(parts) < len(header):
            continue
        row = {header[i]: parts[i].strip().strip('"') for i in range(len(header))}
        rows.append(row)
    grouped: dict[tuple[str, str], list] = defaultdict(list)
    for row in rows:
        title = row.get("Contest Title", "")
        p = row.get("Contest Party", "")
        grouped[(title, p)].append(
            {
                "name": row.get("Candidate Name", ""),
                "party_code": p,
                "party": party_label(p),
                "votes": int(row.get("Total Votes") or 0),
                "source_candidate_id": row.get("Candidate ID", ""),
            }
        )
    contests = []
    for (title, p), cands in grouped.items():
        cands.sort(key=lambda c: (-c["votes"], c["name"]))
        contests.append(
            {
                "office": title,
                "party_code": p,
                "party": party_label(p),
                "candidates": cands,
                "nominee": cands[0] if cands else None,
            }
        )
    return contests


def office_kind(title: str) -> str:
    t = title.lower()
    if t.startswith("u.s. representative"):
        return "us_house"
    if t.startswith("u.s. senator") or t.startswith("u.s. senate"):
        return "us_senate"
    if t == "governor":
        return "governor"
    if t.startswith("lieutenant"):
        return "lt_governor"
    if t.startswith("state senator"):
        return "state_senate"
    if t.startswith("state representative"):
        return "state_house"
    if "trustee" in t:
        return "oha_trustee"
    if t.startswith("mayor"):
        return "mayor"
    if t.startswith("councilmember"):
        return "council"
    return "other"


def district_from_office(title: str) -> str | None:
    m = re.search(r"Dist(?:rict)?\s*(IV|III|II|I|[0-9]+)", title, re.I)
    if not m:
        if "at-large" in title.lower() or "at large" in title.lower():
            return "00"
        return None
    raw = m.group(1).upper()
    roman = {"I": "01", "II": "02", "III": "03", "IV": "04"}
    if raw in roman:
        return roman[raw]
    return raw.zfill(2)


def island_for_zip(zip5: str, county_geoid: str | None) -> str | None:
    if zip5 in MOLOKAI_ZIPS:
        return "Molokaʻi"
    if zip5 in LANAI_ZIPS:
        return "Lānaʻi"
    if county_geoid == "15003":
        return "Oʻahu"
    if county_geoid == "15001":
        return "Hawaiʻi Island"
    if county_geoid == "15007":
        return "Kauaʻi"
    if county_geoid == "15009":
        return "Maui"
    return None


def build_zip_cd(text: str) -> dict[str, list]:
    zips: dict[str, list] = defaultdict(list)
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    for row in reader:
        zcta = (row.get("GEOID_ZCTA5_20") or "").strip()
        geoid = (row.get("GEOID_CD119_20") or "").strip()
        name = (row.get("NAMELSAD_CD119_20") or "").strip()
        land = int(row.get("AREALAND_PART") or 0)
        if len(zcta) != 5 or len(geoid) < 3:
            continue
        if not name:
            continue
        fips = geoid[:2]
        dist = geoid[2:]
        state = FIPS_TO_STATE.get(fips)
        if not state:
            continue
        zips[zcta].append(
            {
                "state": state,
                "state_fips": fips,
                "district": dist,
                "geoid": geoid,
                "name": name,
                "land": land,
            }
        )
    for zcta, items in zips.items():
        items.sort(key=lambda x: -x["land"])
    return zips


def build_zip_county(text: str) -> dict[str, list]:
    zips: dict[str, list] = defaultdict(list)
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    # columns: GEOID_ZCTA5_20, GEOID_COUNTY_20, NAMELSAD_COUNTY_20, AREALAND_PART
    for row in reader:
        zcta = (row.get("GEOID_ZCTA5_20") or "").strip()
        geoid = (row.get("GEOID_COUNTY_20") or "").strip()
        name = (row.get("NAMELSAD_COUNTY_20") or "").strip()
        land = int(row.get("AREALAND_PART") or 0)
        if len(zcta) != 5 or len(geoid) != 5:
            continue
        zips[zcta].append({"geoid": geoid, "name": name, "land": land})
    for items in zips.values():
        items.sort(key=lambda x: -x["land"])
    return zips


def parse_gazetteer_zip(zbytes: bytes) -> dict[str, tuple[float, float]]:
    coords = {}
    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as fh:
            text = fh.read().decode("utf-8", errors="replace")
    # GEOID\t... INTPTLAT INTPTLONG typically last two cols, space/tab
    for i, ln in enumerate(text.splitlines()):
        if i == 0:
            continue
        parts = re.split(r"\s+", ln.strip())
        if len(parts) < 3:
            continue
        geoid = parts[0]
        try:
            lat = float(parts[-2])
            lon = float(parts[-1])
        except ValueError:
            continue
        if len(geoid) == 5:
            coords[geoid] = (lat, lon)
    return coords


def geocode_point(lat: float, lon: float) -> dict | None:
    url = (
        "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
        f"?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current&format=json"
    )
    try:
        data = json.loads(fetch_text(url))
    except Exception:
        return None
    geos = (
        data.get("result", {})
        .get("geographies", {})
    )
    out = {}
    sldu = geos.get("2024 State Legislative Districts - Upper") or geos.get(
        "State Legislative Districts - Upper"
    ) or []
    sldl = geos.get("2024 State Legislative Districts - Lower") or geos.get(
        "State Legislative Districts - Lower"
    ) or []
    if sldu:
        g = sldu[0]
        out["sldu"] = {
            "geoid": g.get("GEOID"),
            "name": g.get("NAME") or g.get("NAMELSAD"),
            "district": str(g.get("SLDUST") or (g.get("GEOID") or "")[-3:]).lstrip("0") or "0",
        }
        # keep 2-digit padded when numeric
        d = re.sub(r"\D", "", out["sldu"]["district"]) or out["sldu"]["district"]
        if d.isdigit():
            out["sldu"]["district"] = d.zfill(2)
    if sldl:
        g = sldl[0]
        out["sldl"] = {
            "geoid": g.get("GEOID"),
            "name": g.get("NAME") or g.get("NAMELSAD"),
            "district": str(g.get("SLDLST") or (g.get("GEOID") or "")[-3:]).lstrip("0") or "0",
        }
        d = re.sub(r"\D", "", out["sldl"]["district"]) or out["sldl"]["district"]
        if d.isdigit():
            out["sldl"]["district"] = d.zfill(2)
    return out or None


FEC_PARTY = {
    "DEM": "Democratic Party",
    "REP": "Republican Party",
    "GRE": "Green Party",
    "LIB": "Libertarian Party",
    "IND": "Independent",
    "NPA": "No Party Affiliation",
    "NON": "Nonpartisan",
    "UNK": "Unknown / not listed",
    "DFL": "Democratic-Farmer-Labor",
    "WTP": "We the People",
    "NNE": "None",
    "OTH": "Other",
    "IND": "Independent",
    "UN": "Unaffiliated",
    "N": "Nonpartisan",
}


def fec_candidates(_api_key: str) -> dict:
    """Parse the FEC candidate master bulk file (cn26) — official, no DEMO_KEY cap."""
    url = "https://www.fec.gov/files/bulk-downloads/2026/cn26.zip"
    zbytes = fetch(url)
    by_state: dict = defaultdict(lambda: {"house": defaultdict(list), "senate": []})
    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        name = next((n for n in zf.namelist() if n.lower().endswith(".txt")), zf.namelist()[0])
        with zf.open(name) as fh:
            text = fh.read().decode("utf-8", errors="replace")
    ici = {"I": "Incumbent", "C": "Challenger", "O": "Open seat"}
    for ln in text.splitlines():
        if not ln.strip():
            continue
        cols = ln.split("|")
        if len(cols) < 9:
            continue
        cand_id, name, pty, year, st, office, dist, ici_code, status = cols[:9]
        if year.strip() != "2026":
            continue
        office = office.strip()
        st = st.strip()
        if office not in {"H", "S"} or st not in STATE_NAME:
            continue
        dist = (dist or "00").strip().zfill(2)
        rec = {
            "name": name.strip(),
            "party": FEC_PARTY.get(pty.strip(), pty.strip() or "Not listed"),
            "office": office,
            "district": dist,
            "candidate_id": cand_id.strip(),
            "incumbent_challenge": ici.get(ici_code.strip(), ici_code.strip()),
            "candidate_status": status.strip(),
            "fec_url": f"https://www.fec.gov/data/candidate/{cand_id.strip()}/",
        }
        if office == "H":
            by_state[st]["house"][dist].append(rec)
        else:
            by_state[st]["senate"].append(rec)
    out = {}
    for st, payload in by_state.items():
        out[st] = {
            "house": dict(payload["house"]),
            "senate": payload["senate"],
        }
    return out


def load_existing_json(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def hawaii_donors_block(existing_hawaii: dict | None, csc: dict | None) -> dict:
    """Keep the committed CSC extract. Do not reset to linked or invent names."""
    if csc:
        filings = (existing_hawaii or {}).get("state_filings") or {}
        return {
            "status": "sourced",
            "path": "/data/csc-donors.json",
            "source_url": csc.get("source_url"),
            "retrieved_at": csc.get("retrieved_at"),
            "counts": csc.get("counts"),
            "reason": csc.get("policy")
            or "Official Hawaii CSC Schedule A extract. Names are never invented. Donor lists are not sold.",
            "cfs_public": filings.get("csc_public") or "https://csc.hawaii.gov/CFSPublic/",
            "csc_searchable": filings.get("csc_searchable")
            or "https://ags.hawaii.gov/campaign/cc/view-searchable-data/",
        }
    prior = ((existing_hawaii or {}).get("state_filings") or {}).get("donors")
    if prior:
        return prior
    return {
        "status": "linked",
        "reason": "Hawaii CSC Schedule A extract is not in this checkout. CFS is linked rather than inventing donor names.",
    }


def parse_house_clerk(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    members = {}
    for mem in root.findall(".//member"):
        info = mem.find("member-info")
        if info is None:
            continue
        sd = (mem.findtext("statedistrict") or "").strip()
        if len(sd) < 3:
            continue
        state = sd[:2]
        dist_raw = sd[2:]
        dist = "00" if dist_raw.upper() in {"00", "AL", "0"} else dist_raw.zfill(2)
        bio = (info.findtext("bioguideID") or "").strip()
        first = (info.findtext("firstname") or "").strip()
        last = (info.findtext("lastname") or "").strip()
        official = (info.findtext("official-name") or f"{first} {last}").strip()
        party = (info.findtext("party") or "").strip()
        slug = re.sub(r"[^a-z]+", "-", f"{first} {last}".lower()).strip("-")
        members[f"{state}-{dist}"] = {
            "name": official,
            "bioguide": bio,
            "party": party,
            "state": state,
            "district": dist,
            "votes_url": f"https://www.congress.gov/member/{slug}/{bio}/votes" if bio else "https://www.congress.gov/members",
            "member_url": f"https://www.congress.gov/member/{slug}/{bio}" if bio else "https://www.congress.gov/members",
            "clerk_url": f"https://clerk.house.gov/Members/{bio}" if bio else "https://clerk.house.gov/",
        }
    return members


def parse_senate(xml_text: str) -> dict:
    # Senate XML uses member elements with state, class, bioguide
    root = ET.fromstring(xml_text)
    by_state: dict[str, list] = defaultdict(list)
    for mem in list(root):
        def txt(*names):
            for n in names:
                v = mem.findtext(n)
                if v:
                    return v.strip()
            return ""
        state = txt("state", "state_code", "stateCode")
        last = txt("last_name", "lastName", "lastname")
        first = txt("first_name", "firstName", "firstname")
        bio = txt("bioguide_id", "bioguideID", "bioguide")
        klass = txt("class", "senator_class", "class_code")
        party = txt("party", "party_code")
        if not state:
            # attributes sometimes
            state = mem.attrib.get("state", "")
        if len(state) != 2:
            continue
        slug = re.sub(r"[^a-z]+", "-", f"{first} {last}".lower()).strip("-")
        by_state[state].append(
            {
                "name": f"{first} {last}".strip(),
                "bioguide": bio,
                "party": party,
                "senate_class": klass,
                "votes_url": f"https://www.congress.gov/member/{slug}/{bio}/votes" if bio else "https://www.senate.gov/",
                "member_url": f"https://www.congress.gov/member/{slug}/{bio}" if bio else "https://www.senate.gov/senators/index.htm",
            }
        )
    return by_state


def compact_zips(zip_cd: dict[str, list], zip_county: dict[str, list], hi_geo: dict) -> dict:
    out = {}
    for zcta, cds in zip_cd.items():
        if not cds:
            continue
        st = cds[0]["state"]
        rec = {
            "s": st,
            "cd": [[c["district"], c["land"], c["name"]] for c in cds if c["land"] > 0 or len(cds) == 1],
        }
        if not rec["cd"]:
            rec["cd"] = [[c["district"], c["land"], c["name"]] for c in cds]
        counties = zip_county.get(zcta) or []
        if counties:
            rec["co"] = counties[0]["name"]
            rec["cog"] = counties[0]["geoid"]
        extra = hi_geo.get(zcta)
        if extra:
            rec.update(extra)
        out[zcta] = rec
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    retrieved = now_iso()
    sources = []

    cd_url = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/tab20_cd11920_zcta520_natl.txt"
    print("Fetching Census CD119 ↔ ZCTA …", flush=True)
    zip_cd = build_zip_cd(fetch_text(cd_url))
    sources.append(source(cd_url, retrieved, "Census 119th Congressional District to 2020 ZCTA relationship file."))

    county_url = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt"
    print("Fetching Census ZCTA ↔ county …", flush=True)
    zip_county = build_zip_county(fetch_text(county_url))
    sources.append(source(county_url, retrieved, "Census 2020 ZCTA to county relationship file."))

    hi_url = "https://elections.hawaii.gov/wp-content/results/2026%20Primary/summary.txt"
    print("Fetching Hawaii Office of Elections 2026 primary summary …", flush=True)
    hi_text = fetch_text(hi_url)
    hi_contests = parse_hi_summary(hi_text)
    sources.append(source(hi_url, retrieved, "Hawaii Office of Elections certified 2026 Primary statewide summary."))
    sources.append(source(
        "https://elections.hawaii.gov/election-results/",
        retrieved,
        "Hawaii Office of Elections results index (2026 Primary certified reports).",
    ))

    # Partisan nominees: highest vote in each party primary for an office.
    nominees_by_office: dict[str, list] = defaultdict(list)
    nonpartisan_fields: dict[str, list] = defaultdict(list)
    for c in hi_contests:
        kind = office_kind(c["office"])
        dist = district_from_office(c["office"])
        entry = {
            "office": c["office"],
            "kind": kind,
            "district": dist,
            "party": c["party"],
            "party_code": c["party_code"],
            "name": c["nominee"]["name"] if c["nominee"] else None,
            "primary_votes": c["nominee"]["votes"] if c["nominee"] else None,
            "field": "general_nominee" if c["party_code"] != "NON" else "certified_primary",
        }
        if c["party_code"] == "NON":
            # Do not infer multi-winner cutoffs. Publish certified primary list.
            nonpartisan_fields[c["office"]] = [
                {
                    "office": c["office"],
                    "kind": kind,
                    "district": dist,
                    "name": cand["name"],
                    "party": c["party"],
                    "primary_votes": cand["votes"],
                    "field": "certified_primary",
                }
                for cand in c["candidates"]
            ]
        else:
            nominees_by_office[c["office"]].append(entry)

    gazetteer_url = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip"
    print("Fetching Census ZCTA gazetteer …", flush=True)
    gaz = parse_gazetteer_zip(fetch(gazetteer_url))
    sources.append(source(gazetteer_url, retrieved, "Census 2024 ZCTA national gazetteer (internal points)."))

    hi_geo = {}
    hi_zips = sorted(z for z, cds in zip_cd.items() if cds and cds[0]["state"] == "HI")
    geo_url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    print(f"Geocoding {len(hi_zips)} Hawaii ZCTAs for 2024 state legislative districts …", flush=True)
    for i, zcta in enumerate(hi_zips, 1):
        county = (zip_county.get(zcta) or [{}])[0]
        rec = {
            "island": island_for_zip(zcta, county.get("geoid")),
        }
        pt = gaz.get(zcta)
        if pt:
            geo = geocode_point(pt[0], pt[1])
            if geo:
                rec.update(geo)
            time.sleep(0.05)
        hi_geo[zcta] = rec
        if i % 20 == 0:
            print(f"  {i}/{len(hi_zips)}", flush=True)
    sources.append(source(
        geo_url,
        retrieved,
        "Census Geocoder Current vintage: 2024 state legislative districts at ZCTA internal points.",
    ))

    # Gold-template confirmation for 96813 from a known official address in the ZIP
    capitol_url = (
        "https://geocoding.geo.census.gov/geocoder/geographies/address"
        "?street=415%20S%20Beretania%20St&city=Honolulu&state=HI&zip=96813"
        "&benchmark=Public_AR_Current&vintage=Current_Current&format=json"
    )
    print("Confirming 96813 via Hawaii State Capitol address …", flush=True)
    try:
        cap = json.loads(fetch_text(capitol_url))
        match = (cap.get("result", {}) or {}).get("addressMatches") or []
        if match:
            geos = match[0].get("geographies") or {}
            sldu = (geos.get("2024 State Legislative Districts - Upper") or [{}])[0]
            sldl = (geos.get("2024 State Legislative Districts - Lower") or [{}])[0]
            point = {
                "address": match[0].get("matchedAddress"),
                "sldu": {
                    "geoid": sldu.get("GEOID"),
                    "name": sldu.get("NAME"),
                    "district": str(sldu.get("SLDUST") or "13").zfill(2),
                },
                "sldl": {
                    "geoid": sldl.get("GEOID"),
                    "name": sldl.get("NAME"),
                    "district": str(sldl.get("SLDLST") or "25").zfill(2),
                },
            }
            existing = hi_geo.get("96813") or {}
            flags = []
            if existing.get("sldu") and existing["sldu"].get("district") != point["sldu"]["district"]:
                flags.append("state_senate")
            if existing.get("sldl") and existing["sldl"].get("district") != point["sldl"]["district"]:
                flags.append("state_house")
            hi_geo["96813"] = {
                **existing,
                "sldu": existing.get("sldu") or point["sldu"],
                "sldl": existing.get("sldl") or point["sldl"],
                "point_check": point,
                "disagreement": flags,
                "island": existing.get("island") or "Oʻahu",
            }
    except Exception as e:
        print("Capitol geocode skipped:", e, flush=True)
    sources.append(source(
        "https://geocoding.geo.census.gov/geocoder/geographies/address",
        retrieved,
        "Census Geocoder address lookup for 415 S Beretania St, Honolulu, HI 96813 (Hawaii State Capitol).",
    ))

    fec_key = os.environ.get("FEC_API_KEY") or "DEMO_KEY"
    print("Fetching FEC 2026 candidate master (cn26 bulk) …", flush=True)
    try:
        federal = fec_candidates(fec_key)
        if not federal:
            raise RuntimeError("FEC bulk parse returned no states")
    except Exception as e:
        prev = OUT / "federal.json"
        if prev.exists():
            print("FEC candidate fetch failed, reusing previous federal.json:", e, flush=True)
            federal = json.loads(prev.read_text(encoding="utf-8"))
        else:
            print("FEC candidate fetch failed, continuing with empty federal map:", e, flush=True)
            federal = {}
    sources.append(source(
        "https://www.fec.gov/files/bulk-downloads/2026/cn26.zip",
        retrieved,
        "FEC candidate master file for the 2025–2026 cycle (House and Senate, election year 2026).",
    ))

    print("Fetching House Clerk member directory …", flush=True)
    clerk_url = "https://clerk.house.gov/xml/lists/MemberData.xml"
    house_members = parse_house_clerk(fetch_text(clerk_url))
    sources.append(source(clerk_url, retrieved, "U.S. House Clerk MemberData.xml (119th Congress)."))

    print("Fetching Senate directory …", flush=True)
    senate_url = "https://www.senate.gov/general/contact_information/senators_cfm.xml"
    try:
        senate_members = parse_senate(fetch_text(senate_url))
    except Exception as e:
        print("Senate XML parse issue:", e, flush=True)
        senate_members = {}
    sources.append(source(senate_url, retrieved, "U.S. Senate senators contact XML."))

    # Class 2 seats are on the 2026 cycle.
    senate_2026_states = set()
    for st, members in senate_members.items():
        for m in members:
            klass = str(m.get("senate_class") or "")
            if "2" in klass or klass.upper() in {"II", "CLASS II"}:
                senate_2026_states.add(st)

    # Federal Schedule A and Hawaii CSC donor extracts are committed JSON
    # (official bulk / SODA). Do not clobber them with OpenFEC or DEMO_KEY.
    existing_donors = load_existing_json(OUT / "donors.json")
    existing_csc = load_existing_json(OUT / "csc-donors.json")
    existing_hawaii = load_existing_json(OUT / "hawaii.json")
    donor_note = (existing_donors or {}).get("policy") or (
        "Official FEC bulk Schedule A individual receipts of $200+ from indiv26.zip. "
        "MEMO_CD=X skipped. Names are never invented. Donor lists are not sold. OpenFEC/DEMO_KEY is not used."
    )
    if existing_donors:
        sources.append(source(
            existing_donors.get("source_url") or "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip",
            existing_donors.get("retrieved_at") or retrieved,
            "Committed FEC bulk Schedule A extract (donors.json). OpenFEC/DEMO_KEY is not used.",
        ))
    sources.append(source(
        "https://www.fec.gov/data/receipts/individual-contributions/",
        retrieved,
        "FEC public individual contribution search (Schedule A).",
    ))
    sources.append(source(
        "https://csc.hawaii.gov/CFSPublic/",
        (existing_csc or {}).get("retrieved_at") or retrieved,
        "Hawaii Campaign Spending Commission Candidate Filing System public site (CFS links kept).",
    ))
    sources.append(source(
        "https://ags.hawaii.gov/campaign/cc/view-searchable-data/",
        (existing_csc or {}).get("retrieved_at") or retrieved,
        "Hawaii CSC searchable candidate committee data landing.",
    ))
    if existing_csc:
        sources.append(source(
            existing_csc.get("source_url") or "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json",
            existing_csc.get("retrieved_at") or retrieved,
            "Committed Hawaii CSC SODA Schedule A extract (csc-donors.json). Street addresses omitted.",
        ))
    sources.append(source(
        "https://elections.hawaii.gov/candidates/candidate-reports/",
        retrieved,
        "Hawaii Office of Elections candidate reports page.",
    ))

    zips_compact = compact_zips(zip_cd, zip_county, hi_geo)

    # Islands → congressional districts (Oʻahu is split)
    islands = {
        "Oʻahu": {
            "state": "HI",
            "cds": ["01", "02"],
            "split": True,
            "note": "Oʻahu includes both HI-01 (urban Honolulu) and HI-02. Enter a ZIP for the district that covers your address.",
            "counties": ["Honolulu County"],
        },
        "Maui": {"state": "HI", "cds": ["02"], "split": False, "counties": ["Maui County"]},
        "Molokaʻi": {"state": "HI", "cds": ["02"], "split": False, "counties": ["Maui County"]},
        "Lānaʻi": {"state": "HI", "cds": ["02"], "split": False, "counties": ["Maui County"]},
        "Kauaʻi": {"state": "HI", "cds": ["02"], "split": False, "counties": ["Kauaʻi County"]},
        "Hawaiʻi Island": {"state": "HI", "cds": ["02"], "split": False, "counties": ["Hawaiʻi County"]},
    }

    hawaii = {
        "election": {
            "jurisdiction": "Hawaii",
            "general_date": "2026-11-03",
            "primary_date": "2026-08-08",
            "primary_certified_source": hi_url,
        },
        "nominees": nominees_by_office,
        "nonpartisan_primary": nonpartisan_fields,
        "geo_by_zip": hi_geo,
        "islands": islands,
        "state_filings": {
            "wired": True,
            "csc_public": "https://csc.hawaii.gov/CFSPublic/",
            "csc_searchable": "https://ags.hawaii.gov/campaign/cc/view-searchable-data/",
            "donors": hawaii_donors_block(existing_hawaii, existing_csc),
        },
    }

    meta = {
        "product": "We The People",
        "user_agent": UA,
        "generated_at": retrieved,
        "general_election_date": "2026-11-03",
        "sources": sources,
        "fec_api_key_present": False,
        "donor_policy": donor_note,
        "rules": [
            "Official and primary sources only.",
            "No Ballotpedia or BallotReady scrape.",
            "No scores.",
            "Every fact has source URL + retrieved_at.",
            "If sources disagree, show both and flag.",
            "Never invent votes or donor names.",
            "Lookup is always free.",
        ],
    }

    # Convert federal house defaultdict-like to plain
    federal_plain = {}
    for st, payload in federal.items():
        house = payload.get("house") or {}
        if hasattr(house, "items"):
            house = dict(house)
        senate_on_ballot = st in senate_2026_states
        federal_plain[st] = {
            "name": STATE_NAME.get(st, st),
            "house": house,
            "senate": payload.get("senate") or [],
            "senate_regular_2026": senate_on_ballot,
            "state_filings_wired": st == "HI",
            "state_filings_note": None
            if st == "HI"
            else "State filings not wired yet. Federal House/Senate filings from the FEC are shown.",
        }

    incumbents = {"house": house_members, "senate": senate_members}

    (OUT / "zips.json").write_text(json.dumps(zips_compact, separators=(",", ":")), encoding="utf-8")
    (OUT / "hawaii.json").write_text(json.dumps(hawaii, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "federal.json").write_text(json.dumps(federal_plain, ensure_ascii=False), encoding="utf-8")
    (OUT / "incumbents.json").write_text(json.dumps(incumbents, ensure_ascii=False), encoding="utf-8")
    if existing_donors:
        print("Preserving committed donors.json (FEC bulk extract; not rewriting via OpenFEC).", flush=True)
    else:
        (OUT / "donors.json").write_text(
            json.dumps(
                {
                    "fec_api_key_present": False,
                    "policy": donor_note,
                    "by_candidate": {},
                    "retrieved_at": retrieved,
                    "source_url": "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip",
                    "reason": "FEC bulk Schedule A extract is not in this checkout. Names are not invented.",
                    "do_not_sell_donor_lists": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    if existing_csc:
        print("Preserving committed csc-donors.json (Hawaii CSC SODA extract).", flush=True)
    if (OUT / "congress-votes.json").exists():
        print("Preserving committed congress-votes.json (House Clerk EVS + Senate LIS).", flush=True)
    if (OUT / "hawaii-votes.json").exists():
        print("Preserving committed hawaii-votes.json (named Hawaii measure-status votes).", flush=True)
    if (OUT / "wa" / "pdc-donors.json").exists():
        print("Preserving committed wa/pdc-donors.json (Washington PDC SODA extract).", flush=True)
    if (OUT / "wa.json").exists():
        print("Preserving committed wa.json (Washington state module stub).", flush=True)
    if (OUT / "co" / "tracer-donors.json").exists():
        print("Preserving committed co/tracer-donors.json (Colorado TRACER bulk extract).", flush=True)
    if (OUT / "co.json").exists():
        print("Preserving committed co.json (Colorado state module stub).", flush=True)
    if (OUT / "ca" / "candidates.json").exists():
        print("Preserving committed ca/candidates.json (CA SOS certified list).", flush=True)
    if (OUT / "ca" / "votes.json").exists():
        print("Preserving committed ca/votes.json (Clerk EVS + Senate LIS).", flush=True)
    if (OUT / "ca" / "calaccess-donors.json").exists():
        print("Preserving committed ca/calaccess-donors.json (CAL-ACCESS RCPT extract).", flush=True)
    if (OUT / "wa" / "votes.json").exists():
        print("Preserving committed wa/votes.json (Clerk EVS + Senate LIS).", flush=True)
    if (OUT / "wa" / "candidates.json").exists():
        print("Preserving committed wa/candidates.json (VoteWA GENERAL 2026 list).", flush=True)
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print("ZIPs", len(zips_compact), "HI contests", len(hi_contests), "federal states", len(federal_plain))
    for test in ("96813", "90210", "82001"):
        print(test, json.dumps(zips_compact.get(test), ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
