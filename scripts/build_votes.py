#!/usr/bin/env python3
"""Official first-run vote extracts. House Clerk EVS, Senate LIS, Hawaii measure status.

Names and vote_cast are copied from official text only. Unnamed unanimous / majority
tallies are not expanded into per-member Ayes. No Ballotpedia. No scores.
"""

from __future__ import annotations

import html as htmlmod
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
CACHE = Path("/tmp/votes")
CACHE.mkdir(parents=True, exist_ok=True)

FROZEN = {
    "congress_rows": 200,
    "per_incumbent": 50,
    "hawaii_named": 1241,
    "hawaii_house_sitting": 51,
    "hawaii_senate_sitting": 25,
    "retrieved_at": "2026-08-31T14:39:52Z",
}

HOUSE = {
    "C001055": {"incumbent_name": "Ed Case", "district": "HI-01", "chamber": "House"},
    "T000487": {"incumbent_name": "Jill Tokuda", "district": "HI-02", "chamber": "House"},
}
SENATE = {
    "Hirono": {"incumbent_name": "Mazie K. Hirono", "bioguide_id": "H001042", "district": None, "chamber": "Senate"},
    "Schatz": {"incumbent_name": "Brian Schatz", "bioguide_id": "S001194", "district": None, "chamber": "Senate"},
}

NONE_RE = re.compile(r"^(none|none\.|0\s*\(none\)|\(none\)|)$", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path | None = None, retries: int = 3) -> bytes:
    if dest and dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes()
    last = None
    for i in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if dest:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            return data
        except Exception as e:
            last = e
            time.sleep(0.4 * (i + 1))
    raise RuntimeError(f"fetch failed {url}: {last}")


def parse_house_index_max() -> int:
    text = fetch("https://clerk.house.gov/evs/2026/index.asp", CACHE / "house_index.asp").decode("latin-1", "replace")
    nums = [int(n) for n in re.findall(r"rollnumber=(\d+)", text, re.I)]
    nums += [int(n) for n in re.findall(r">(\d{1,4})</A></TD>", text)]
    if not nums:
        raise RuntimeError("House EVS index had no roll numbers")
    return max(nums)


def parse_senate_menu_max() -> int:
    xml = fetch(
        "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml",
        CACHE / "senate_menu_119_2.xml",
    )
    root = ET.fromstring(xml)
    nums = [int((v.findtext("vote_number") or "0").lstrip("0") or "0") for v in root.findall(".//vote")]
    if not nums:
        raise RuntimeError("Senate LIS vote menu had no vote numbers")
    return max(nums)


def house_tally(meta: ET.Element) -> str:
    tot = meta.find(".//totals-by-vote")
    if tot is None:
        return ""
    y = tot.findtext("yea-total") or "0"
    n = tot.findtext("nay-total") or "0"
    p = tot.findtext("present-total") or "0"
    nv = tot.findtext("not-voting-total") or "0"
    return f"Yeas {y}, Nays {n}, Present {p}, Not Voting {nv}"


def house_votes(retrieved: str, latest: int, take: int = 50) -> list[dict]:
    start = max(1, latest - take + 1)
    rows = []
    for num in range(latest, start - 1, -1):
        url = f"https://clerk.house.gov/evs/2026/roll{num}.xml"
        dest = CACHE / "house" / f"roll{num}.xml"
        try:
            raw = fetch(url, dest)
        except Exception as e:
            print(f"  house roll {num} skip: {e}", flush=True)
            continue
        root = ET.fromstring(raw)
        meta = root.find("vote-metadata")
        if meta is None:
            continue
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
            "retrieved_at": retrieved,
        }
        for rec in root.findall(".//recorded-vote"):
            leg = rec.find("legislator")
            if leg is None:
                continue
            bio = leg.attrib.get("name-id")
            if bio not in HOUSE:
                continue
            cast = (rec.findtext("vote") or "").strip()
            if not cast:
                continue
            info = HOUSE[bio]
            rows.append(
                {
                    **base,
                    "incumbent_name": info["incumbent_name"],
                    "bioguide_id": bio,
                    "district": info["district"],
                    "vote_cast": cast,
                }
            )
        print(f"  house roll {num}", flush=True)
    return rows


def senate_votes(retrieved: str, latest: int, take: int = 50) -> list[dict]:
    start = max(1, latest - take + 1)
    rows = []
    for num in range(latest, start - 1, -1):
        url = f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_{num:05d}.xml"
        dest = CACHE / "senate" / f"vote_{num:05d}.xml"
        try:
            raw = fetch(url, dest)
        except Exception as e:
            print(f"  senate vote {num} skip: {e}", flush=True)
            continue
        root = ET.fromstring(raw)
        yeas = root.findtext(".//yeas") or root.findtext(".//count/yeas") or ""
        nays = root.findtext(".//nays") or root.findtext(".//count/nays") or ""
        if not yeas:
            # some files nest under vote_tally
            yeas = root.findtext(".//vote_tally/yeas") or ""
            nays = root.findtext(".//vote_tally/nays") or ""
        tally = f"Yeas {yeas}, Nays {nays}".strip(", ")
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
            "tally": tally,
            "source_url": url,
            "source_name": "U.S. Senate LIS roll-call vote XML",
            "retrieved_at": retrieved,
            "district": None,
        }
        for mem in root.findall(".//member"):
            last = (mem.findtext("last_name") or "").strip()
            if last not in SENATE:
                continue
            cast = (mem.findtext("vote_cast") or "").strip()
            if not cast:
                continue
            info = SENATE[last]
            rows.append(
                {
                    **base,
                    "incumbent_name": info["incumbent_name"],
                    "bioguide_id": info["bioguide_id"],
                    "vote_cast": cast,
                }
            )
        print(f"  senate vote {num}", flush=True)
    return rows


def split_names(blob: str) -> list[str]:
    blob = htmlmod.unescape(blob).strip().rstrip(".")
    blob = re.sub(r"\s+", " ", blob)
    if NONE_RE.match(blob) or re.match(r"^none\b", blob, re.I):
        return []
    parts = [p.strip() for p in blob.split(",") if p.strip()]
    names: list[str] = []
    for p in parts:
        if re.fullmatch(r"[A-Z]\.?", p):
            if names:
                names[-1] = f"{names[-1]}, {p}"
            continue
        names.append(p)
    out = []
    for n in names:
        if NONE_RE.match(n) or n.lower() == "none":
            continue
        out.append(n)
    return out


def strip_title(blob: str) -> str:
    return re.sub(r"^(Representative\(s\)|Senator\(s\)|Rep\.|Sen\.)\s+", "", blob.strip(), flags=re.I)


ROW_RE = re.compile(
    r'class="date-label"><font[^>]*>([^<]+)</font></td>\s*'
    r'<td[^>]*><font[^>]*>([HS])</font></td>\s*'
    r"<td><font[^>]*>(.*?)</font></td>",
    re.I | re.S,
)

# Committee / conference fully-named blocks.
COMMITTEE_BLOCK = re.compile(
    r"The votes(?:\s+in\s+[A-Z0-9/]+)?(?:\s+of the (?:Senate|House) Conference Managers)? were as follows:\s*(.+)$",
    re.I,
)
AYES_NAMED = re.compile(
    r"(\d+\s+)?Ayes?(?:\(s\))?:\s*(Representative\(s\)|Senator\(s\))\s+([^;]+)",
    re.I,
)
RES_NAMED = re.compile(
    r"Ayes?(?:\(s\))? with reservations:\s*(?:(Representative\(s\)|Senator\(s\))\s+)?([^;]+)",
    re.I,
)
NOES_NAMED = re.compile(
    r"(?:\d+\s+)?No(?:es|e)?(?:\(es\))?:\s*(?:(Representative\(s\)|Senator\(s\))\s+)?([^;]+)",
    re.I,
)
EXC_NAMED = re.compile(
    r"(?:\d+\s+)?Excused:\s*(?:(Representative\(s\)|Senator\(s\))\s+)?([^;.]+)",
    re.I,
)

# Floor House: names immediately before the official verb.
FLOOR_RES = re.compile(
    r"Representative\(s\)\s+(.+?)\s+voting aye with reservations",
    re.I,
)
FLOOR_NO = re.compile(
    r"Representative\(s\)\s+(.+?)\s+voting no(?:\s+\(\d+\))?",
    re.I,
)
FLOOR_EXC = re.compile(
    r"Representative\(s\)\s+(.+?)\s+excused(?:\s+\(\d+\))?",
    re.I,
)

# Floor Senate-style named subsets. Unnamed "Ayes, 25" is not expanded.
PAREN_NO = re.compile(r"Noes?,\s*\d+\s*\((?:Senator\(s\)|Representative\(s\))\s*([^)]+)\)", re.I)
PAREN_EXC = re.compile(r"Excused,\s*\d+\s*\((?:Senator\(s\)|Representative\(s\))\s*([^)]+)\)", re.I)
COLON_RES = re.compile(
    r"Aye\(s\) with reservations:\s*(?:Senator\(s\)|Representative\(s\))\s*([^.;]+)",
    re.I,
)


def parse_named_from_status(text: str, chamber: str) -> list[tuple[str, str]]:
    """Return (member_name, vote_cast) from official status text. Never invent unnamed Ayes."""
    text = htmlmod.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    found: list[tuple[str, str]] = []

    def add(names: list[str], cast: str):
        for n in names:
            n = n.strip().rstrip(".")
            if n and not NONE_RE.match(n) and not re.search(r"\b(voting|none)\b|\(\d+\)", n, re.I):
                found.append((n, cast))

    comm = COMMITTEE_BLOCK.search(text)
    if comm:
        block = comm.group(1)
        m = AYES_NAMED.search(block)
        if m:
            add(split_names(strip_title(m.group(3))), "Aye")
        m = RES_NAMED.search(block)
        if m:
            add(split_names(strip_title((m.group(2) or ""))), "Aye with reservations")
        m = NOES_NAMED.search(block)
        if m:
            add(split_names(strip_title(m.group(2) or "")), "No")
        m = EXC_NAMED.search(block)
        if m:
            add(split_names(strip_title(m.group(2) or "")), "Excused")
        return found

    # Floor House named subsets. Parse one clause at a time so a later
    # "voting no" cannot swallow an earlier reservations list.
    if "The votes were as follows" not in text:
        clauses = re.split(r";|\band\s+(?=Representative\(s\))", text)
        for clause in clauses:
            m = FLOOR_RES.search(clause)
            if m and not re.match(r"none\b", m.group(1).strip(), re.I):
                add(split_names(m.group(1)), "Aye with reservations")
            if "none voting no" not in clause.lower():
                m = FLOOR_NO.search(clause)
                if m and not re.match(r"none\b", m.group(1).strip(), re.I):
                    add(split_names(m.group(1)), "No")
            m = FLOOR_EXC.search(clause)
            if m and not re.match(r"none\b", m.group(1).strip(), re.I):
                add(split_names(m.group(1)), "Excused")

    m = COLON_RES.search(text)
    if m and not re.match(r"none\b", m.group(1).strip(), re.I):
        add(split_names(m.group(1)), "Aye with reservations")
    m = PAREN_NO.search(text)
    if m and not re.match(r"none\b", m.group(1).strip(), re.I):
        add(split_names(m.group(1)), "No")
    m = PAREN_EXC.search(text)
    if m and not re.match(r"none\b", m.group(1).strip(), re.I):
        add(split_names(m.group(1)), "Excused")
    return found


def parse_measure_html(html: str, measure: str, source_url: str, retrieved: str) -> list[dict]:
    rows = []
    for date_s, chamber_c, status in ROW_RE.findall(html):
        date_s = date_s.strip()
        # Keep 2026-dated named votes on 2026 measure pages (carryover 2025 unnamed/named stay
        # unexpanded / out of the 2026 first-run unless dated 2026).
        if not re.search(r"2026", date_s):
            continue
        status_plain = re.sub(r"<[^>]+>", " ", status)
        named = parse_named_from_status(status_plain, chamber_c)
        if not named:
            continue
        question = status_plain.strip()
        # Short question: first clause
        qshort = re.split(r"\. | with Representative| with Senator| The votes", question, maxsplit=1)[0].strip()
        for name, cast in named:
            rows.append(
                {
                    "incumbent_name": name,
                    "bioguide_id": None,
                    "chamber": "House" if chamber_c == "H" else "Senate",
                    "district": None,
                    "congress": None,
                    "session": "2026 Regular Session",
                    "roll_call_number": None,
                    "vote_date": date_s,
                    "question": qshort,
                    "measure": measure,
                    "vote_desc": question.strip(),
                    "vote_cast": cast,
                    "result": None,
                    "tally": None,
                    "source_url": source_url,
                    "source_name": "Hawaii State Legislature measure status",
                    "retrieved_at": retrieved,
                }
            )
    return rows


def rss_measure_list() -> list[tuple[str, int]]:
    listing = fetch(
        "https://data.capitol.hawaii.gov/sessions/session2026/rss/",
        CACHE / "rss_index.html",
    ).decode("utf-8", "replace")
    hrefs = re.findall(r'href="([^"]+\.xml)"', listing, re.I)
    out = []
    seen = set()
    for h in hrefs:
        name = h.rsplit("/", 1)[-1]
        m = re.match(r"([A-Z]+)(\d+)\.xml$", name, re.I)
        if not m:
            continue
        typ, num = m.group(1).upper(), int(m.group(2))
        if typ not in {"HB", "SB", "HR", "SR", "HCR", "SCR"}:
            continue
        key = (typ, num)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return sorted(out)


def hawaii_votes(retrieved: str) -> tuple[list[dict], dict]:
    measures = rss_measure_list()
    print(f"Hawaii 2026 measures in official RSS: {len(measures)}", flush=True)
    rows: list[dict] = []
    errors = 0
    fetched = 0

    def one(typ: str, num: int):
        url = f"https://data.capitol.hawaii.gov/session/measure_indiv.aspx?billnumber={num}&billtype={typ}&year=2026"
        dest = CACHE / "hi" / f"{typ}{num}.html"
        raw = fetch(url, dest)
        measure = f"{typ}{num}"
        return parse_measure_html(raw.decode("utf-8", "replace"), measure, url, retrieved)

    workers = 12
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(one, typ, num): (typ, num) for typ, num in measures}
        for i, fut in enumerate(as_completed(futs), 1):
            typ, num = futs[fut]
            try:
                got = fut.result()
                rows.extend(got)
                fetched += 1
            except Exception as e:
                errors += 1
                if errors <= 8:
                    print(f"  skip {typ}{num}: {e}", flush=True)
            if i % 400 == 0:
                print(f"  hawaii {i}/{len(measures)} named so far {len(rows)}", flush=True)
    # Public file: floor named votes only. Committee named rolls are counted
    # but not shipped, so unnamed floor Ayes are never inferred from them.
    floor = []
    committee_n = 0
    for r in rows:
        desc = r.get("vote_desc") or ""
        if re.search(r"The votes (were as follows|in |of the )", desc):
            committee_n += 1
            continue
        name = re.sub(r"[)\]].*$", "", r["incumbent_name"]).strip(" .")
        if not name or len(name) < 2:
            continue
        r = {**r, "incumbent_name": name, "kind": "floor_named"}
        floor.append(r)
    rows = floor
    stats["committee_named"] = committee_n
    house_names = {r["incumbent_name"] for r in rows if r["chamber"] == "House"}
    senate_names = {r["incumbent_name"] for r in rows if r["chamber"] == "Senate"}
    stats = {
        "measures_listed": len(measures),
        "pages_fetched": fetched,
        "fetch_errors": errors,
        "named_votes": len(rows),
        "house_names_seen": len(house_names),
        "senate_names_seen": len(senate_names),
        "house_names": sorted(house_names),
        "senate_names": sorted(senate_names),
    }
    return rows, stats


def write_congress(rows: list[dict], retrieved: str, house_max: int, senate_max: int) -> dict:
    by = defaultdict(list)
    for r in rows:
        by[r["bioguide_id"]].append(r)
    counts = {k: len(v) for k, v in by.items()}
    flags = []
    if len(rows) != FROZEN["congress_rows"]:
        flags.append(
            {
                "field": "congress_rows",
                "frozen": FROZEN["congress_rows"],
                "this_extract": len(rows),
                "note": "Kept this official Clerk/LIS count. Votes are not invented to match the freeze.",
            }
        )
    for bio, info in {**{b: HOUSE[b] for b in HOUSE}, **{SENATE[n]["bioguide_id"]: SENATE[n] for n in SENATE}}.items():
        n = counts.get(bio, 0)
        if n != FROZEN["per_incumbent"]:
            flags.append(
                {
                    "field": bio,
                    "frozen": FROZEN["per_incumbent"],
                    "this_extract": n,
                    "incumbent_name": info["incumbent_name"],
                }
            )
    payload = {
        "policy": (
            "Official U.S. House Clerk EVS XML (2026 rolls) and U.S. Senate LIS roll-call XML "
            "for Hawaii incumbents. vote_cast is the exact official text. Votes are never invented. "
            "No Ballotpedia. No scores."
        ),
        "retrieved_at": retrieved,
        "source_url": "https://clerk.house.gov/evs/2026/index.asp",
        "sources": [
            {
                "url": "https://clerk.house.gov/evs/2026/index.asp",
                "retrieved_at": retrieved,
                "note": f"House Clerk EVS 2026 index; latest roll {house_max}. Example roll https://clerk.house.gov/evs/2026/roll283.xml",
            },
            {
                "url": "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml",
                "retrieved_at": retrieved,
                "note": f"Senate LIS 119th Congress 2nd session vote menu; latest vote {senate_max}.",
            },
        ],
        "user_agent": UA,
        "row_count": len(rows),
        "by_incumbent": {
            bio: {
                "incumbent_name": (HOUSE.get(bio) or next(v for v in SENATE.values() if v["bioguide_id"] == bio))[
                    "incumbent_name"
                ],
                "item_count_all": len(items),
                "items": items,
            }
            for bio, items in by.items()
        },
        "votes": rows,
        "prior_extract": {"retrieved_at": FROZEN["retrieved_at"], "row_count": FROZEN["congress_rows"], "per_incumbent": 50},
        "disagreement_flags": flags,
    }
    (OUT / "congress-votes.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def write_hawaii(rows: list[dict], stats: dict, retrieved: str) -> dict:
    flags = []
    if len(rows) != FROZEN["hawaii_named"]:
        flags.append(
            {
                "field": "named_votes",
                "frozen": FROZEN["hawaii_named"],
                "this_extract": len(rows),
                "note": "Kept this official named-vote count. Unnamed unanimous floor tallies were not expanded.",
            }
        )
    if stats["house_names_seen"] != FROZEN["hawaii_house_sitting"]:
        flags.append(
            {
                "field": "house_sitting_names_seen",
                "frozen": FROZEN["hawaii_house_sitting"],
                "this_extract": stats["house_names_seen"],
                "note": "Count of distinct House names that appear in named official status text, not a forced roster.",
            }
        )
    if stats["senate_names_seen"] != FROZEN["hawaii_senate_sitting"]:
        flags.append(
            {
                "field": "senate_sitting_names_seen",
                "frozen": FROZEN["hawaii_senate_sitting"],
                "this_extract": stats["senate_names_seen"],
                "note": "Count of distinct Senate names that appear in named official status text, not a forced roster.",
            }
        )
    by = defaultdict(list)
    for r in rows:
        by[r["incumbent_name"]].append(r)
    payload = {
        "policy": (
            "Official Hawaii State Legislature measure status pages (2026). Named votes only. "
            "Unnamed unanimous or majority floor tallies are not expanded into per-member Ayes. "
            "capitol.hawaii.gov returned 403 from this extractor; the same official measure_indiv "
            "pages were retrieved from data.capitol.hawaii.gov with User-Agent WeThePeople-CivicBot/1.0. "
            "Votes are never invented. No Ballotpedia. No scores."
        ),
        "retrieved_at": retrieved,
        "source_url": "https://data.capitol.hawaii.gov/session/measure_indiv.aspx",
        "landing_url": "https://www.capitol.hawaii.gov/",
        "capitol_hawaii_gov_status": "403 Forbidden with CivicBot UA; used official data.capitol.hawaii.gov host of the same measure status pages.",
        "user_agent": UA,
        "row_count": len(rows),
        "sitting": {
            "house_names_seen": stats["house_names_seen"],
            "senate_names_seen": stats["senate_names_seen"],
            "house_frozen": FROZEN["hawaii_house_sitting"],
            "senate_frozen": FROZEN["hawaii_senate_sitting"],
        },
        "counts": {
            "named_votes": len(rows),
            "measures_listed": stats["measures_listed"],
            "pages_fetched": stats["pages_fetched"],
            "fetch_errors": stats["fetch_errors"],
        },
        "by_member": {
            name: {"incumbent_name": name, "item_count_all": len(items), "items": items}
            for name, items in sorted(by.items())
        },
        "votes": rows,
        "prior_extract": {
            "retrieved_at": FROZEN["retrieved_at"],
            "named_votes": FROZEN["hawaii_named"],
            "house_sitting": 51,
            "senate_sitting": 25,
        },
        "disagreement_flags": flags,
        "unnamed_tallies_unexpanded": True,
    }
    path = OUT / "hawaii-votes.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if path.stat().st_size < 200:
        raise SystemExit("Refusing to ship an empty hawaii-votes.json")
    return payload


def main() -> int:
    retrieved = now_iso()
    print("House EVS index …", flush=True)
    house_max = parse_house_index_max()
    print("Senate LIS menu …", flush=True)
    senate_max = parse_senate_menu_max()
    print(f"Latest official rolls: House {house_max}, Senate {senate_max}", flush=True)
    print("Fetching House Clerk EVS (latest 50) …", flush=True)
    hrows = house_votes(retrieved, house_max, 50)
    print("Fetching Senate LIS (latest 50) …", flush=True)
    srows = senate_votes(retrieved, senate_max, 50)
    congress = hrows + srows
    cpay = write_congress(congress, retrieved, house_max, senate_max)
    print("congress-votes.json", cpay["row_count"], "flags", cpay["disagreement_flags"], flush=True)

    print("Fetching Hawaii measure status (named votes only) …", flush=True)
    hi_rows, stats = hawaii_votes(retrieved)
    hpay = write_hawaii(hi_rows, stats, retrieved)
    print("hawaii-votes.json", hpay["row_count"], "house names", stats["house_names_seen"], "senate names", stats["senate_names_seen"], flush=True)
    print("flags", hpay["disagreement_flags"], flush=True)
    # sanity: Iwamoto / HB389
    hits = [r for r in hi_rows if r["measure"] == "HB389" and "Iwamoto" in r["incumbent_name"]]
    print("HB389 Iwamoto rows", hits, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
