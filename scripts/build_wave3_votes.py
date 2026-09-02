#!/usr/bin/env python3
"""Official Clerk EVS 253-292 + Senate LIS 202-231 votes for PA/OH/GA/NC/NJ sitting members."""

from __future__ import annotations

import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T15:58:08Z"
RETRIEVED_BY_STATE = {
    "PA": "2026-09-02T15:58:08Z",
    "OH": "2026-09-02T15:58:08Z",
    "GA": "2026-09-02T15:58:08Z",
    "NC": "2026-09-02T15:58:08Z",
    "NJ": "2026-09-02T15:58:08Z",
}
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
CACHE = Path("/tmp/votes-wave2")
HOUSE_CACHE = Path("/tmp/votes-ca-wa/house")
SENATE_CACHE = Path("/tmp/votes-ca-wa/senate")
MEMBERDATA_URL = "https://clerk.house.gov/xml/lists/MemberData.xml"
SENATORS_URL = "https://www.senate.gov/general/contact_information/senators_cfm.xml"
HOUSE_ROLLS = range(253, 293)
SENATE_VOTES = range(202, 232)

# Sitting House + Senate vote math from Clerk/LIS (vacant seats skipped).
# House 40 rolls (253-292) + Senate 30 rolls (202-231) = 40×sitting + 60,
# except GA-13 Everton Blair Jr. sworn 2026-09-01 (7 of 40 House rolls).
# Official GA extract is 527 House + 60 Senate = 587. Votes are never invented.
EXPECT = {
    "PA": {"house": 17, "votes": 740, "vacant": []},
    "OH": {"house": 15, "votes": 660, "vacant": []},
    "GA": {"house": 14, "votes": 587, "vacant": []},
    "NC": {"house": 14, "votes": 620, "vacant": []},
    "NJ": {"house": 12, "votes": 540, "vacant": []},
}

LEG_INDEX = {
    "PA": [
        {"label": "Pennsylvania General Assembly (official)", "url": "https://www.legis.state.pa.us/"},
        {"label": "Pennsylvania House of Representatives", "url": "https://www.legis.state.pa.us/cfdocs/legis/home/member_information/mbrList.cfm?body=H"},
        {"label": "Pennsylvania Senate", "url": "https://www.legis.state.pa.us/cfdocs/legis/home/member_information/mbrList.cfm?body=S"},
    ],
    "OH": [
        {"label": "Ohio Legislature (official)", "url": "https://www.legislature.ohio.gov/"},
        {"label": "Ohio House of Representatives", "url": "https://ohiohouse.gov/"},
        {"label": "Ohio Senate", "url": "https://ohiosenate.gov/"},
    ],
    "GA": [
        {"label": "Georgia General Assembly (official)", "url": "https://www.legis.ga.gov/"},
        {"label": "Georgia House of Representatives", "url": "https://www.legis.ga.gov/house"},
        {"label": "Georgia Senate", "url": "https://www.legis.ga.gov/senate"},
    ],
    "NC": [
        {"label": "North Carolina General Assembly (official)", "url": "https://www.ncleg.gov/"},
        {"label": "North Carolina House of Representatives", "url": "https://www.ncleg.gov/House"},
        {"label": "North Carolina Senate", "url": "https://www.ncleg.gov/Senate"},
    ],
    "NJ": [
        {"label": "New Jersey Legislature (official)", "url": "https://www.njleg.state.nj.us/"},
        {"label": "New Jersey General Assembly", "url": "https://www.njleg.state.nj.us/legislative-roster?chamber=G"},
        {"label": "New Jersey Senate", "url": "https://www.njleg.state.nj.us/legislative-roster?chamber=S"},
    ],
}

STATE_NAME = {
    "PA": "Pennsylvania",
    "OH": "Ohio",
    "GA": "Georgia",
    "NC": "North Carolina",
    "NJ": "New Jersey",
}


def fetch(url: str, dest: Path, retries: int = 4) -> bytes:
    if dest.exists() and dest.stat().st_size > 200:
        return dest.read_bytes()
    last = None
    for i in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "application/xml,text/xml,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return data
        except Exception as exc:
            last = exc
            time.sleep(0.5 * (2**i))
    raise RuntimeError(f"fetch failed {url}: {last}")


def house_xml(num: int) -> Path:
    cached = HOUSE_CACHE / f"roll{num}.xml"
    if cached.exists() and cached.stat().st_size > 200:
        return cached
    dest = CACHE / "house" / f"roll{num}.xml"
    fetch(f"https://clerk.house.gov/evs/2026/roll{num}.xml", dest)
    return dest


def senate_xml(num: int) -> Path:
    cached = SENATE_CACHE / f"vote_{num:05d}.xml"
    if cached.exists() and cached.stat().st_size > 200:
        return cached
    dest = CACHE / "senate" / f"vote_{num:05d}.xml"
    fetch(
        f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_{num:05d}.xml",
        dest,
    )
    return dest


def load_house(states: list[str]) -> dict[str, tuple[dict[str, tuple[str, str]], list[dict]]]:
    raw = fetch(MEMBERDATA_URL, CACHE / "MemberData.xml")
    if not (CACHE / "MemberData.xml").exists() and Path("/tmp/votes-az/MemberData.xml").exists():
        raw = Path("/tmp/votes-az/MemberData.xml").read_bytes()
    root = ET.fromstring(raw)
    out: dict[str, tuple[dict[str, tuple[str, str]], list[dict]]] = {
        st: ({}, []) for st in states
    }
    for mem in root.findall(".//member"):
        info = mem.find("member-info")
        if info is None:
            continue
        statedist = (mem.findtext("statedistrict") or "").strip()
        state = next((st for st in states if statedist.startswith(st) and statedist[len(st) :].isdigit()), None)
        if not state:
            continue
        dist_num = statedist[len(state) :]
        dist = f"{state}-{int(dist_num):02d}"
        bio = (info.findtext("bioguideID") or "").strip()
        name = (info.findtext("official-name") or "").strip()
        footnote = (info.findtext("footnote") or "").strip()
        sitting, vacant = out[state]
        if not bio or not name:
            vacant.append({"district": dist, "note": footnote or "Vacant seat; skipped in federal vote extract."})
            continue
        sitting[bio] = (name, dist)
    for state, (sitting, vacant) in out.items():
        exp = EXPECT[state]
        if len(sitting) != exp["house"]:
            raise SystemExit(f"{state} sitting House {len(sitting)} != {exp['house']}")
        got_vacant = {v["district"] for v in vacant}
        if set(exp["vacant"]) != got_vacant:
            raise SystemExit(f"{state} vacant {got_vacant} != {exp['vacant']}")
    return out


def load_senate(states: list[str]) -> dict[str, dict[tuple[str, str], tuple[str, str]]]:
    raw = fetch(SENATORS_URL, CACHE / "senators.xml")
    root = ET.fromstring(raw)
    out: dict[str, dict[tuple[str, str], tuple[str, str]]] = {st: {} for st in states}
    for mem in root.findall(".//member"):
        last = (mem.findtext("last_name") or "").strip()
        first = (mem.findtext("first_name") or "").strip()
        st = (mem.findtext("state") or "").strip()
        bio = (mem.findtext("bioguide_id") or "").strip()
        if st not in out:
            continue
        name = f"{first} {last}".strip()
        if not last or not name or not bio:
            raise SystemExit(f"Senate contact XML missing official {st} senator fields")
        out[st][(last, st)] = (name, bio)
    for st, rows in out.items():
        if len(rows) != 2:
            raise SystemExit(f"expected 2 sitting {st} senators, got {len(rows)}")
    return out


def house_tally(meta: ET.Element) -> str:
    tot = meta.find(".//totals-by-vote")
    if tot is None:
        return ""
    y = tot.findtext("yea-total") or "0"
    n = tot.findtext("nay-total") or "0"
    p = tot.findtext("present-total") or "0"
    nv = tot.findtext("not-voting-total") or "0"
    return f"Yeas {y}, Nays {n}, Present {p}, Not Voting {nv}"


def download_rolls() -> None:
    jobs = []
    for num in HOUSE_ROLLS:
        url = f"https://clerk.house.gov/evs/2026/roll{num}.xml"
        dest = HOUSE_CACHE / f"roll{num}.xml"
        if not dest.exists():
            dest = CACHE / "house" / f"roll{num}.xml"
        jobs.append((url, dest))
    for num in SENATE_VOTES:
        url = f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_{num:05d}.xml"
        dest = SENATE_CACHE / f"vote_{num:05d}.xml"
        if not dest.exists():
            dest = CACHE / "senate" / f"vote_{num:05d}.xml"
        jobs.append((url, dest))
    print(f"downloading {len(jobs)} official XML files", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch, url, dest): url for url, dest in jobs}
        done = 0
        for fut in as_completed(futs):
            fut.result()
            done += 1
            if done % 10 == 0 or done == len(jobs):
                print(f"  fetched {done}/{len(jobs)}", flush=True)


def parse_house(state: str, delegation: dict[str, tuple[str, str]], retrieved_at: str = RETRIEVED) -> list[dict]:
    rows: list[dict] = []
    for num in HOUSE_ROLLS:
        url = f"https://clerk.house.gov/evs/2026/roll{num}.xml"
        raw = house_xml(num).read_bytes()
        root = ET.fromstring(raw)
        meta = root.find("vote-metadata")
        if meta is None:
            raise RuntimeError(f"missing vote-metadata {url}")
        base = {
            "chamber": "House",
            "congress": int(meta.findtext("congress") or 119),
            "session": (meta.findtext("session") or "").strip(),
            "roll_call_number": int(meta.findtext("rollcall-num") or num),
            "vote_date": (meta.findtext("action-date") or "").strip(),
            "question": (meta.findtext("vote-question") or "").strip(),
            "measure": (meta.findtext("legis-num") or "").strip(),
            "vote_desc": (meta.findtext("vote-desc") or "").strip(),
            "result": (meta.findtext("vote-result") or "").strip(),
            "tally": house_tally(meta),
            "source_url": url,
            "source_name": "U.S. House Clerk EVS XML",
        }
        for rec in root.findall(".//recorded-vote"):
            leg = rec.find("legislator")
            if leg is None:
                continue
            bio = (leg.attrib.get("name-id") or "").strip()
            if bio not in delegation:
                continue
            cast = (rec.findtext("vote") or "").strip()
            if not cast:
                continue
            name, dist = delegation[bio]
            rows.append(
                {
                    **base,
                    "state": state,
                    "incumbent_name": name,
                    "bioguide_id": bio,
                    "district": dist,
                    "vote_cast": cast,
                    "retrieved_at": retrieved_at,
                }
            )
    return rows


def parse_senate(state: str, delegation: dict[tuple[str, str], tuple[str, str]], retrieved_at: str = RETRIEVED) -> list[dict]:
    rows: list[dict] = []
    for num in SENATE_VOTES:
        url = f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_{num:05d}.xml"
        raw = senate_xml(num).read_bytes()
        root = ET.fromstring(raw)
        yeas = root.findtext(".//yeas") or ""
        nays = root.findtext(".//nays") or ""
        if not yeas:
            yeas = root.findtext(".//vote_tally/yeas") or ""
            nays = root.findtext(".//vote_tally/nays") or ""
        base = {
            "chamber": "Senate",
            "congress": int(root.findtext("congress") or 119),
            "session": (root.findtext("session") or "").strip(),
            "roll_call_number": int(root.findtext("vote_number") or num),
            "vote_date": (root.findtext("vote_date") or "").strip(),
            "question": (root.findtext("question") or root.findtext("vote_question_text") or "").strip(),
            "measure": (root.findtext(".//document_name") or root.findtext("vote_document_text") or "").strip(),
            "vote_desc": (root.findtext("vote_title") or root.findtext("vote_document_text") or "").strip(),
            "result": (root.findtext("vote_result") or "").strip(),
            "tally": f"Yeas {yeas}, Nays {nays}".strip(", "),
            "source_url": url,
            "source_name": "U.S. Senate LIS roll-call vote XML",
            "district": None,
        }
        for mem in root.findall(".//member"):
            last = (mem.findtext("last_name") or "").strip()
            st = (mem.findtext("state") or "").strip()
            info = delegation.get((last, st))
            if not info:
                continue
            cast = (mem.findtext("vote_cast") or "").strip()
            if not cast:
                continue
            name, bio = info
            rows.append(
                {
                    **base,
                    "state": state,
                    "incumbent_name": name,
                    "bioguide_id": bio,
                    "vote_cast": cast,
                    "retrieved_at": retrieved_at,
                }
            )
    return rows


def write_state(state: str, house_rows: list[dict], senate_rows: list[dict], house, senate, vacant) -> None:
    rows = sorted(
        house_rows + senate_rows,
        key=lambda r: (
            0 if r["chamber"] == "House" else 1,
            -(r.get("roll_call_number") or 0),
            r.get("bioguide_id") or "",
        ),
    )
    exp = EXPECT[state]
    if len(rows) != exp["votes"]:
        raise SystemExit(f"{state} votes {len(rows)} != {exp['votes']}")
    for vac in exp["vacant"]:
        if any((r.get("district") or "") == vac for r in rows):
            raise SystemExit(f"{vac} vacant seat must not appear in vote rows")
    counts = Counter(r["bioguide_id"] for r in rows)
    skip = [f"{d} vacant" for d in exp["vacant"]]
    if state == "GA":
        skip.append("GA-13 Everton Blair Jr. sworn 2026-09-01; earlier Clerk rolls 253-285 have no recorded vote for this member")
    dest_dir = OUT / state.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)
    votes = {
        "policy": (
            "Official U.S. House Clerk EVS XML (2026 unpadded rolls 253-292) and U.S. Senate LIS "
            f"roll-call XML (119th Congress 2nd session votes 202-231) for sitting {state} members. "
            "House match is name-id==bioguide from Clerk MemberData.xml. "
            "Senate match is last name + state; names/bioguides from senate.gov contact XML. "
            + (("Vacant " + ", ".join(exp["vacant"]) + " skipped. ") if exp["vacant"] else "")
            + (
                "GA-13 Everton Blair Jr. sworn September 1, 2026 after the David Scott vacancy; "
                "only Clerk rolls after that swearing are present (7 of 40). "
                if state == "GA"
                else ""
            )
            + "vote_cast is the exact official text. Votes are never invented. No Ballotpedia. No scores."
        ),
        "retrieved_at": RETRIEVED_BY_STATE[state],
        "state": state,
        "count": len(rows),
        "counts_by_member": dict(sorted(counts.items())),
        "votes": rows,
        "method": {
            "house": {
                "source": "https://clerk.house.gov/evs/2026/index.asp",
                "rolls": "253-292",
                "url_pattern": "https://clerk.house.gov/evs/2026/roll{N}.xml",
                "match": "legislator name-id == Clerk MemberData bioguideID",
                "memberdata": MEMBERDATA_URL,
            },
            "senate": {
                "source": "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml",
                "votes": "202-231",
                "url_pattern": "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_{NNNNN}.xml",
                "match": "member last_name + state",
                "names": SENATORS_URL,
            },
            "skip": skip,
            "user_agent": UA,
        },
    }
    (dest_dir / "votes.json").write_text(json.dumps(votes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    delegation = {
        "state": state,
        "retrieved_at": RETRIEVED_BY_STATE[state],
        "source_url": MEMBERDATA_URL,
        "house": [
            {
                "bioguide": bio,
                "name": name,
                "district": dist,
                "votes_url": f"https://clerk.house.gov/Members/{bio}",
            }
            for bio, (name, dist) in sorted(house.items(), key=lambda kv: kv[1][1])
        ],
        "senate": [
            {
                "bioguide": bio,
                "name": name,
                "last_name": last,
                "votes_url": f"https://www.congress.gov/member/{bio}",
            }
            for (last, st), (name, bio) in sorted(senate.items())
        ],
        "vacant": vacant,
    }
    (dest_dir / "congress-delegation.json").write_text(
        json.dumps(delegation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (dest_dir / "legislature-vote-index.json").write_text(
        json.dumps(
            {
                "state": state,
                "kind": "legislature_vote_index",
                "note": "Official source URL index only. State legislative floor votes are not extracted in this populate.",
                "retrieved_at": RETRIEVED_BY_STATE[state],
                "sources": LEG_INDEX[state],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    stub_path = OUT / f"{state.lower()}.json"
    if stub_path.exists():
        stub = json.loads(stub_path.read_text(encoding="utf-8"))
    else:
        stub = {}
    stub.setdefault("election", {})
    stub["election"]["jurisdiction"] = STATE_NAME[state]
    stub["election"]["state_code"] = state
    note = stub["election"].get("note") or ""
    if "Clerk/LIS" not in note:
        if state == "NC":
            stub["election"]["note"] = (
                "Official NCSBE 2026 Candidate_Listing_2026.csv (primary + general; November list "
                "not yet final), Clerk/LIS federal votes, and federal FEC Schedule A $200+. "
                "State campaign-finance bulk is pending. Donor lists are not sold."
            )
        else:
            stub["election"]["note"] = (
                f"Official {STATE_NAME[state]} Clerk/LIS federal votes and 2026 House/Senate "
                "federal FEC Schedule A $200+. State ballots are pending until official lists "
                "clear. State campaign-finance bulk is pending. Donor lists are not sold."
            )
    stub["votes_path"] = f"/data/{state.lower()}/votes.json"
    stub["congress_delegation_path"] = f"/data/{state.lower()}/congress-delegation.json"
    stub["legislature_vote_index_path"] = f"/data/{state.lower()}/legislature-vote-index.json"
    stub.setdefault("nominees", {})
    stub.setdefault("geo_by_zip", {})
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": "https://clerk.house.gov/evs/2026/index.asp", "retrieved_at": RETRIEVED_BY_STATE[state]},
        {"url": "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml", "retrieved_at": RETRIEVED_BY_STATE[state]},
        {"url": MEMBERDATA_URL, "retrieved_at": RETRIEVED_BY_STATE[state], "note": "Clerk MemberData sitting House members"},
        {"url": SENATORS_URL, "retrieved_at": RETRIEVED_BY_STATE[state], "note": "Senate.gov sitting senators"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
        else:
            for existing in sources:
                if existing.get("url") == src["url"]:
                    existing["retrieved_at"] = RETRIEVED_BY_STATE[state]
    stub_path.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{state} votes={len(rows)} house={len(house_rows)} senate={len(senate_rows)} vacant={vacant}", flush=True)


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    states = list(EXPECT)
    house_all = load_house(states)
    senate_all = load_senate(states)
    download_rolls()
    for state in states:
        sitting, vacant = house_all[state]
        house_rows = parse_house(state, sitting, RETRIEVED_BY_STATE[state])
        senate_rows = parse_senate(state, senate_all[state], RETRIEVED_BY_STATE[state])
        write_state(state, house_rows, senate_rows, sitting, senate_all[state], vacant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
