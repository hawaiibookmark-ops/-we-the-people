#!/usr/bin/env python3
"""Official CA/WA federal vote extracts from House Clerk EVS and Senate LIS."""

from __future__ import annotations

import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
CACHE = Path("/tmp/votes-ca-wa")
CACHE.mkdir(parents=True, exist_ok=True)

HOUSE_ROLLS = range(253, 293)  # 253–292 inclusive
SENATE_VOTES = range(202, 232)  # 202–231 inclusive

CA_HOUSE = {
    "G000607": ("James Gallagher", "CA-01"),
    "H001068": ("Jared Huffman", "CA-02"),
    "K000401": ("Kevin Kiley", "CA-03"),
    "T000460": ("Mike Thompson", "CA-04"),
    "M001177": ("Tom McClintock", "CA-05"),
    "B001287": ("Ami Bera", "CA-06"),
    "M001163": ("Doris O. Matsui", "CA-07"),
    "G000559": ("John Garamendi", "CA-08"),
    "H001090": ("Josh Harder", "CA-09"),
    "D000623": ("Mark DeSaulnier", "CA-10"),
    "P000197": ("Nancy Pelosi", "CA-11"),
    "S001231": ("Lateefah Simon", "CA-12"),
    "G000605": ("Adam Gray", "CA-13"),
    # CA-14 vacant — skipped
    "M001225": ("Kevin Mullin", "CA-15"),
    "L000607": ("Sam T. Liccardo", "CA-16"),
    "K000389": ("Ro Khanna", "CA-17"),
    "L000397": ("Zoe Lofgren", "CA-18"),
    "P000613": ("Jimmy Panetta", "CA-19"),
    "F000480": ("Vince Fong", "CA-20"),
    "C001059": ("Jim Costa", "CA-21"),
    "V000129": ("David G. Valadao", "CA-22"),
    "O000019": ("Jay Obernolte", "CA-23"),
    "C001112": ("Salud O. Carbajal", "CA-24"),
    "R000599": ("Raul Ruiz", "CA-25"),
    "B001285": ("Julia Brownley", "CA-26"),
    "W000830": ("George Whitesides", "CA-27"),
    "C001080": ("Judy Chu", "CA-28"),
    "R000620": ("Luz M. Rivas", "CA-29"),
    "F000483": ("Laura Friedman", "CA-30"),
    "C001123": ("Gilbert Ray Cisneros, Jr.", "CA-31"),
    "S000344": ("Brad Sherman", "CA-32"),
    "A000371": ("Pete Aguilar", "CA-33"),
    "G000585": ("Jimmy Gomez", "CA-34"),
    "T000474": ("Norma J. Torres", "CA-35"),
    "L000582": ("Ted Lieu", "CA-36"),
    "K000400": ("Sydney Kamlager-Dove", "CA-37"),
    "S001156": ("Linda T. Sánchez", "CA-38"),
    "T000472": ("Mark Takano", "CA-39"),
    "K000397": ("Young Kim", "CA-40"),
    "C000059": ("Ken Calvert", "CA-41"),
    "G000598": ("Robert Garcia", "CA-42"),
    "W000187": ("Maxine Waters", "CA-43"),
    "B001300": ("Nanette Diaz Barragán", "CA-44"),
    "T000491": ("Derek Tran", "CA-45"),
    "C001110": ("J. Luis Correa", "CA-46"),
    "M001241": ("Dave Min", "CA-47"),
    "I000056": ("Darrell Issa", "CA-48"),
    "L000593": ("Mike Levin", "CA-49"),
    "P000608": ("Scott H. Peters", "CA-50"),
    "J000305": ("Sara Jacobs", "CA-51"),
    "V000130": ("Juan Vargas", "CA-52"),
}
WA_HOUSE = {
    "D000617": ("Suzan K. DelBene", "WA-01"),
    "L000560": ("Rick Larsen", "WA-02"),
    "G000600": ("Marie Gluesenkamp Perez", "WA-03"),
    "N000189": ("Dan Newhouse", "WA-04"),
    "B001322": ("Michael Baumgartner", "WA-05"),
    "R000621": ("Emily Randall", "WA-06"),
    "J000298": ("Pramila Jayapal", "WA-07"),
    "S001216": ("Kim Schrier", "WA-08"),
    "S000510": ("Adam Smith", "WA-09"),
    "S001159": ("Marilyn Strickland", "WA-10"),
}
# Senate: last name + state
SENATE = {
    ("Schiff", "CA"): ("Adam B. Schiff", "S001150"),
    ("Padilla", "CA"): ("Alex Padilla", "P000145"),
    ("Cantwell", "WA"): ("Maria Cantwell", "C000127"),
    ("Murray", "WA"): ("Patty Murray", "M001111"),
}

HOUSE_BY_STATE = {"CA": CA_HOUSE, "WA": WA_HOUSE}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return data
        except Exception as e:
            last = e
            time.sleep(0.5 * (2**i))
    raise RuntimeError(f"fetch failed {url}: {last}")


def house_tally(meta: ET.Element) -> str:
    tot = meta.find(".//totals-by-vote")
    if tot is None:
        return ""
    y = tot.findtext("yea-total") or "0"
    n = tot.findtext("nay-total") or "0"
    p = tot.findtext("present-total") or "0"
    nv = tot.findtext("not-voting-total") or "0"
    return f"Yeas {y}, Nays {n}, Present {p}, Not Voting {nv}"


def download_all() -> None:
    jobs = []
    for num in HOUSE_ROLLS:
        jobs.append(
            (
                f"https://clerk.house.gov/evs/2026/roll{num}.xml",
                CACHE / "house" / f"roll{num}.xml",
            )
        )
    for num in SENATE_VOTES:
        jobs.append(
            (
                f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_{num:05d}.xml",
                CACHE / "senate" / f"vote_{num:05d}.xml",
            )
        )
    print(f"downloading {len(jobs)} official XML files", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch, url, dest): url for url, dest in jobs}
        done = 0
        for fut in as_completed(futs):
            url = futs[fut]
            fut.result()
            done += 1
            if done % 10 == 0 or done == len(jobs):
                print(f"  fetched {done}/{len(jobs)}", flush=True)


def parse_house() -> list[dict]:
    rows = []
    for num in HOUSE_ROLLS:
        url = f"https://clerk.house.gov/evs/2026/roll{num}.xml"
        raw = (CACHE / "house" / f"roll{num}.xml").read_bytes()
        root = ET.fromstring(raw)
        meta = root.find("vote-metadata")
        if meta is None:
            raise RuntimeError(f"missing vote-metadata {url}")
        retrieved = now_iso()
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
        wanted = {**CA_HOUSE, **WA_HOUSE}
        for rec in root.findall(".//recorded-vote"):
            leg = rec.find("legislator")
            if leg is None:
                continue
            bio = (leg.attrib.get("name-id") or "").strip()
            if bio not in wanted:
                continue
            cast = (rec.findtext("vote") or "").strip()
            if not cast:
                continue
            name, dist = wanted[bio]
            st = dist[:2]
            rows.append(
                {
                    **base,
                    "state": st,
                    "incumbent_name": name,
                    "bioguide_id": bio,
                    "district": dist,
                    "vote_cast": cast,
                }
            )
    return rows


def parse_senate() -> list[dict]:
    rows = []
    for num in SENATE_VOTES:
        url = f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_{num:05d}.xml"
        raw = (CACHE / "senate" / f"vote_{num:05d}.xml").read_bytes()
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
            info = SENATE.get((last, st))
            if not info:
                continue
            cast = (mem.findtext("vote_cast") or "").strip()
            if not cast:
                continue
            name, bio = info
            rows.append(
                {
                    **base,
                    "state": st,
                    "incumbent_name": name,
                    "bioguide_id": bio,
                    "vote_cast": cast,
                }
            )
    return rows


def write_state(state: str, rows: list[dict], retrieved: str) -> None:
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
            f"Official U.S. House Clerk EVS XML (2026 unpadded rolls 253-292) and U.S. Senate LIS "
            f"roll-call XML (119th Congress 2nd session votes 202-231) for {state} members. "
            "House match is name-id==bioguide. Senate match is last name + state. "
            "vote_cast is the exact official text. Votes are never invented. "
            "Vacant CA-14 is skipped. No Ballotpedia. No scores."
        ),
        "retrieved_at": retrieved,
        "state": state,
        "count": len(rows),
        "counts_by_member": dict(sorted(counts.items())),
        "votes": rows,
        "method": {
            "house": {
                "source": "https://clerk.house.gov/evs/2026/index.asp",
                "rolls": "253-292",
                "url_pattern": "https://clerk.house.gov/evs/2026/roll{N}.xml",
                "match": "legislator name-id == bioguide",
            },
            "senate": {
                "source": "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml",
                "votes": "202-231",
                "url_pattern": "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_{NNNNN}.xml",
                "match": "member last_name + state",
            },
            "skip": ["CA-14 vacant"] if state == "CA" else [],
            "user_agent": UA,
        },
    }
    dest_dir = OUT / state.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "votes.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest_dir / 'votes.json'} count={len(rows)} members={len(counts)}", flush=True)


def write_delegation(state: str, retrieved: str) -> None:
    house = HOUSE_BY_STATE[state]
    senate = [(k, v) for k, v in SENATE.items() if k[1] == state]
    payload = {
        "state": state,
        "retrieved_at": retrieved,
        "source_url": "https://www.congress.gov/members",
        "house": [
            {
                "bioguide": bio,
                "name": name,
                "district": dist,
                "votes_url": f"https://clerk.house.gov/Members/{bio}",
            }
            for bio, (name, dist) in house.items()
        ],
        "senate": [
            {
                "bioguide": bio,
                "name": name,
                "last_name": last,
                "votes_url": f"https://www.congress.gov/member/{bio}",
            }
            for (last, st), (name, bio) in senate
        ],
        "vacant": (
            [{"district": "CA-14", "note": "Vacant seat; skipped in federal vote extract."}]
            if state == "CA"
            else []
        ),
    }
    dest = OUT / state.lower() / "congress-delegation.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_leg_index(state: str, retrieved: str) -> None:
    if state == "CA":
        sources = [
            {
                "label": "California Legislature bill information (official vote history on measure pages)",
                "url": "https://leginfo.legislature.ca.gov/",
            },
            {
                "label": "California Assembly Clerk roll-call / Daily Journal",
                "url": "https://clerk.assembly.ca.gov/",
            },
            {
                "label": "California Senate Floor votes",
                "url": "https://www.senate.ca.gov/floor-votes",
            },
        ]
    else:
        sources = [
            {
                "label": "Washington State Legislature bill information",
                "url": "https://app.leg.wa.gov/billinfo/",
            },
            {
                "label": "Washington State Legislature roll calls",
                "url": "https://leg.wa.gov/",
            },
        ]
    payload = {
        "state": state,
        "kind": "legislature_vote_index",
        "note": "Official source URL index only. State legislative floor votes are not extracted in this populate.",
        "retrieved_at": retrieved,
        "sources": sources,
    }
    dest = OUT / state.lower() / "legislature-vote-index.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_state_stub(state: str, retrieved: str) -> None:
    stub_path = OUT / f"{state.lower()}.json"
    if stub_path.exists():
        stub = json.loads(stub_path.read_text(encoding="utf-8"))
    else:
        stub = {
            "election": {
                "jurisdiction": "California" if state == "CA" else "Washington",
                "state_code": state,
                "general_date": "2026-11-03" if state == "CA" else None,
            },
            "state_filings": {},
            "nominees": {},
            "geo_by_zip": {},
            "sources": [],
        }
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    stub["votes_path"] = f"/data/{state.lower()}/votes.json"
    stub["congress_delegation_path"] = f"/data/{state.lower()}/congress-delegation.json"
    stub["legislature_vote_index_path"] = f"/data/{state.lower()}/legislature-vote-index.json"
    if "state_filings" not in stub or not isinstance(stub["state_filings"], dict):
        stub["state_filings"] = {}
    if donors:
        stub["state_filings"]["donors"] = donors
    sources = stub.get("sources") or []
    extra = [
        {"url": "https://clerk.house.gov/evs/2026/index.asp", "retrieved_at": retrieved},
        {"url": "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml", "retrieved_at": retrieved},
    ]
    have = {s.get("url") for s in sources if isinstance(s, dict)}
    for s in extra:
        if s["url"] not in have:
            sources.append(s)
    stub["sources"] = sources
    stub_path.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged stub {stub_path} donors_status={(donors or {}).get('status')}", flush=True)


def main() -> int:
    retrieved = now_iso()
    download_all()
    house_rows = parse_house()
    senate_rows = parse_senate()
    print(f"parsed house={len(house_rows)} senate={len(senate_rows)}", flush=True)
    for state in ("CA", "WA"):
        rows = [r for r in house_rows + senate_rows if r["state"] == state]
        for r in rows:
            r["retrieved_at"] = retrieved
        write_state(state, rows, retrieved)
        write_delegation(state, retrieved)
        write_leg_index(state, retrieved)
        merge_state_stub(state, retrieved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
