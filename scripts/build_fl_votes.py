#!/usr/bin/env python3
"""Official Florida federal votes from House Clerk EVS and Senate LIS."""

from __future__ import annotations

import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
RETRIEVED = "2026-09-02T12:53:50Z"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
CACHE = Path("/tmp/votes-fl")
HOUSE_CACHE = Path("/tmp/votes-ca-wa/house")
SENATE_CACHE = Path("/tmp/votes-ca-wa/senate")
MEMBERDATA_URL = "https://clerk.house.gov/xml/lists/MemberData.xml"
SENATORS_URL = "https://www.senate.gov/general/contact_information/senators_cfm.xml"
HOUSE_ROLLS = range(253, 293)
SENATE_VOTES = range(202, 232)
VACANT_DISTRICT = "FL-20"
EXPECTED_HOUSE_SITTING = 27
EXPECTED_VOTES = 1140


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


def load_house_delegation() -> tuple[dict[str, tuple[str, str]], list[dict]]:
    raw = fetch(MEMBERDATA_URL, CACHE / "MemberData.xml")
    root = ET.fromstring(raw)
    out: dict[str, tuple[str, str]] = {}
    vacant: list[dict] = []
    for mem in root.findall(".//member"):
        info = mem.find("member-info")
        if info is None:
            continue
        state_el = info.find("state")
        postal = state_el.attrib.get("postal-code") if state_el is not None else ""
        statedist = (mem.findtext("statedistrict") or "").strip()
        if postal != "FL" and not statedist.startswith("FL"):
            continue
        if not statedist.startswith("FL"):
            continue
        dist_num = statedist[2:]
        if not dist_num.isdigit():
            raise SystemExit(f"unexpected Clerk statedistrict {statedist!r}")
        dist = f"FL-{int(dist_num):02d}"
        bio = (info.findtext("bioguideID") or "").strip()
        name = (info.findtext("official-name") or "").strip()
        footnote = (info.findtext("footnote") or "").strip()
        if not bio or not name:
            vacant.append(
                {
                    "district": dist,
                    "note": footnote or "Vacant seat; skipped in federal vote extract.",
                }
            )
            continue
        out[bio] = (name, dist)
    if len(out) != EXPECTED_HOUSE_SITTING:
        raise SystemExit(
            f"expected {EXPECTED_HOUSE_SITTING} sitting FL House members from Clerk, got {len(out)}"
        )
    if not any(v.get("district") == VACANT_DISTRICT for v in vacant):
        raise SystemExit(f"Clerk MemberData did not flag vacant {VACANT_DISTRICT}")
    return out, vacant


def load_senate_delegation() -> dict[tuple[str, str], tuple[str, str]]:
    raw = fetch(SENATORS_URL, CACHE / "senators.xml")
    root = ET.fromstring(raw)
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for mem in root.findall(".//member"):
        last = (mem.findtext("last_name") or "").strip()
        first = (mem.findtext("first_name") or "").strip()
        st = (mem.findtext("state") or "").strip()
        bio = (mem.findtext("bioguide_id") or "").strip()
        if st != "FL":
            continue
        name = f"{first} {last}".strip()
        if not last or not name or not bio:
            raise SystemExit("Senate contact XML missing official FL senator fields")
        out[(last, st)] = (name, bio)
    if len(out) != 2:
        raise SystemExit(f"expected 2 sitting FL senators from senate.gov, got {len(out)}")
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


def parse_house(delegation: dict[str, tuple[str, str]]) -> list[dict]:
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
                    "state": "FL",
                    "incumbent_name": name,
                    "bioguide_id": bio,
                    "district": dist,
                    "vote_cast": cast,
                    "retrieved_at": RETRIEVED,
                }
            )
    return rows


def parse_senate(delegation: dict[tuple[str, str], tuple[str, str]]) -> list[dict]:
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
                    "state": "FL",
                    "incumbent_name": name,
                    "bioguide_id": bio,
                    "vote_cast": cast,
                    "retrieved_at": RETRIEVED,
                }
            )
    return rows


def write_votes(rows: list[dict]) -> None:
    rows = sorted(
        rows,
        key=lambda r: (
            0 if r["chamber"] == "House" else 1,
            -(r.get("roll_call_number") or 0),
            r.get("bioguide_id") or "",
        ),
    )
    counts = Counter(r["bioguide_id"] for r in rows)
    payload = {
        "policy": (
            "Official U.S. House Clerk EVS XML (2026 unpadded rolls 253-292) and U.S. Senate LIS "
            "roll-call XML (119th Congress 2nd session votes 202-231) for sitting FL members. "
            "House match is name-id==bioguide from Clerk MemberData.xml. "
            "Senate match is last name + state; names/bioguides from senate.gov contact XML. "
            f"Vacant {VACANT_DISTRICT} is skipped. vote_cast is the exact official text. "
            "Votes are never invented. No Ballotpedia. No scores."
        ),
        "retrieved_at": RETRIEVED,
        "state": "FL",
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
            "skip": [f"{VACANT_DISTRICT} vacant"],
            "user_agent": UA,
        },
    }
    dest = OUT / "fl" / "votes.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest} count={len(rows)} members={len(counts)}", flush=True)


def write_delegation(
    house: dict[str, tuple[str, str]],
    senate: dict[tuple[str, str], tuple[str, str]],
    vacant: list[dict],
) -> None:
    payload = {
        "state": "FL",
        "retrieved_at": RETRIEVED,
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
    dest = OUT / "fl" / "congress-delegation.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_leg_index() -> None:
    payload = {
        "state": "FL",
        "kind": "legislature_vote_index",
        "note": "Official source URL index only. State legislative floor votes are not extracted in this populate.",
        "retrieved_at": RETRIEVED,
        "sources": [
            {
                "label": "Florida Senate (official)",
                "url": "https://www.flsenate.gov/",
            },
            {
                "label": "Florida House of Representatives (official)",
                "url": "https://www.myfloridahouse.gov/",
            },
        ],
    }
    dest = OUT / "fl" / "legislature-vote-index.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_stub() -> None:
    stub_path = OUT / "fl.json"
    stub = json.loads(stub_path.read_text(encoding="utf-8"))
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    election = stub.setdefault("election", {})
    election["jurisdiction"] = "Florida"
    election["state_code"] = "FL"
    election["note"] = (
        "Official Florida DOS 2026 general candidate extracts (state + local) and Clerk/LIS "
        "federal votes. State campaign-finance bulk is pending (no standing statewide bulk "
        "URL; access is form-limited). Federal FEC Schedule A $200+ may land later. Donor "
        "lists are not sold."
    )
    stub["votes_path"] = "/data/fl/votes.json"
    stub["congress_delegation_path"] = "/data/fl/congress-delegation.json"
    stub["legislature_vote_index_path"] = "/data/fl/legislature-vote-index.json"
    if donors:
        stub.setdefault("state_filings", {})["donors"] = donors
    sources = stub.setdefault("sources", [])
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    extra = [
        {"url": "https://clerk.house.gov/evs/2026/index.asp", "retrieved_at": RETRIEVED},
        {
            "url": "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml",
            "retrieved_at": RETRIEVED,
        },
        {"url": MEMBERDATA_URL, "retrieved_at": RETRIEVED, "note": "Clerk MemberData sitting House members"},
        {"url": SENATORS_URL, "retrieved_at": RETRIEVED, "note": "Senate.gov sitting senators"},
    ]
    for src in extra:
        if src["url"] not in have:
            sources.append(src)
    stub_path.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged stub {stub_path} donors_status={(donors or {}).get('status')}", flush=True)


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    house, vacant = load_house_delegation()
    senate = load_senate_delegation()
    download_rolls()
    house_rows = parse_house(house)
    senate_rows = parse_senate(senate)
    rows = house_rows + senate_rows
    print(f"parsed house={len(house_rows)} senate={len(senate_rows)} total={len(rows)}", flush=True)
    if len(rows) != EXPECTED_VOTES:
        raise SystemExit(
            f"expected {EXPECTED_VOTES} FL federal votes "
            f"({EXPECTED_HOUSE_SITTING}x40 + 2x30), got {len(rows)}"
        )
    if any((r.get("district") or "") == VACANT_DISTRICT for r in rows):
        raise SystemExit(f"{VACANT_DISTRICT} vacant seat must not appear in vote rows")
    write_votes(rows)
    write_delegation(house, senate, vacant)
    write_leg_index()
    merge_stub()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
