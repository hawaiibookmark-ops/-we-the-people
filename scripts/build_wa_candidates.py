#!/usr/bin/env python3
"""Parse official VoteWA GENERAL 2026 CandidateList (election 899) into candidates.json."""

from __future__ import annotations

import csv
import html as htmlmod
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from http.cookiejar import CookieJar
from pathlib import Path

UA = "WeThePeople-CivicBot/1.0"
LIST_URL = "https://voter.votewa.gov/CandidateList.aspx?e=899"
RETRIEVED = "2026-09-02T11:16:22Z"
ELECTION_ID = "899"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data" / "wa"
STUB = ROOT / "public" / "data" / "wa.json"
CACHE = Path("/tmp/wa-votewa")

COUNTIES = [
    ("01", "Adams"),
    ("02", "Asotin"),
    ("03", "Benton"),
    ("04", "Chelan"),
    ("05", "Clallam"),
    ("06", "Clark"),
    ("07", "Columbia"),
    ("08", "Cowlitz"),
    ("09", "Douglas"),
    ("10", "Ferry"),
    ("11", "Franklin"),
    ("12", "Garfield"),
    ("13", "Grant"),
    ("14", "Grays Harbor"),
    ("15", "Island"),
    ("16", "Jefferson"),
    ("17", "King"),
    ("18", "Kitsap"),
    ("19", "Kittitas"),
    ("20", "Klickitat"),
    ("21", "Lewis"),
    ("22", "Lincoln"),
    ("23", "Mason"),
    ("24", "Okanogan"),
    ("25", "Pacific"),
    ("26", "Pend Oreille"),
    ("27", "Pierce"),
    ("28", "San Juan"),
    ("29", "Skagit"),
    ("30", "Skamania"),
    ("34", "Snohomish"),
    ("32", "Spokane"),
    ("33", "Stevens"),
    ("31", "Thurston"),
    ("35", "Wahkiakum"),
    ("36", "Walla Walla"),
    ("37", "Whatcom"),
    ("38", "Whitman"),
    ("39", "Yakima"),
]

ROW_RE = re.compile(
    r'<tr class="rg(?:Alt)?Row"[^>]*>\s*'
    r"<td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td>"
    r"<td>(.*?)</td>",
    re.S | re.I,
)
HREF_RE = re.compile(
    r'genericvoterguide\.aspx\?e=(\d+)&(?:amp;)?c=([^"#]*)#/candidates/(\d+)/(\d+)"[^>]*>([^<]+)',
    re.I,
)
POSTBACK_RE = re.compile(r"__doPostBack\(&#39;([^&]+?)&#39;,\s*&#39;([^&]*?)&#39;\)")


def opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def http(op: urllib.request.OpenerDirector, data: dict | None = None, retries: int = 5) -> tuple[bytes, str]:
    headers = {"User-Agent": UA, "Referer": LIST_URL, "Accept": "text/html,application/xhtml+xml,text/csv;q=0.9,*/*;q=0.8"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Origin"] = "https://voter.votewa.gov"
        body = urllib.parse.urlencode(data).encode()
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(LIST_URL, data=body, headers=headers)
            with op.open(req, timeout=90) as resp:
                return resp.read(), resp.headers.get("Content-Type") or ""
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            wait = 3 * (2**attempt)
            print(f"retry attempt={attempt + 1} wait={wait}s err={exc}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"VoteWA request failed: {last}")


def hiddens(page: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"<input[^>]+>", page, re.I):
        tag = m.group(0)
        if "hidden" not in tag.lower():
            continue
        n = re.search(r'name="([^"]+)"', tag)
        v = re.search(r'value="([^"]*)"', tag)
        if n:
            out[n.group(1)] = htmlmod.unescape(v.group(1) if v else "")
    return out


def form_fields(page: str, county: str = "") -> dict[str, str]:
    fields = hiddens(page)
    fields["ctl00$ContentPlaceHolder1$ddlElection"] = ELECTION_ID
    fields["ctl00$ContentPlaceHolder1$ddlCounty"] = county
    fields.setdefault("ctl00$ContentPlaceHolder1$hidElectionDate", "GENERAL 2026")
    fields.setdefault("ctl00$ContentPlaceHolder1$hidElectionType", "General")
    return fields


def strip_tags(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def parse_grid_rows(page: str) -> list[dict]:
    rows: list[dict] = []
    for m in ROW_RE.finditer(page):
        dtype, district, race, term, length, name_cell = m.groups()
        href = HREF_RE.search(name_cell)
        name = strip_tags(name_cell)
        rec = {
            "district_type": strip_tags(dtype),
            "district": strip_tags(district),
            "race": strip_tags(race),
            "term_type": strip_tags(term),
            "term_length": strip_tags(length),
            "candidate_name": name,
            "race_id": href.group(3) if href else None,
            "candidate_id": href.group(4) if href else None,
            "county_code": (href.group(2) if href else "") or None,
        }
        rows.append(rec)
    return rows


def pager_targets(page: str) -> list[str]:
    targets: list[str] = []
    for m in POSTBACK_RE.finditer(page):
        target = htmlmod.unescape(m.group(1))
        if "grdCandidates" in target and "ctl03" in target and "Export" not in target:
            if target not in targets:
                targets.append(target)
    return targets


def current_page(page: str) -> int | None:
    m = re.search(r'class="rgCurrentPage"[^>]*>\s*<span>(\d+)</span>', page)
    return int(m.group(1)) if m else None


def page_count_label(page: str) -> tuple[int | None, int | None]:
    off = re.search(r'id="lblOfficeCount"[^>]*>(\d+)', page)
    cand = re.search(r'id="lblCandidateCount"[^>]*>(\d+)', page)
    return (int(off.group(1)) if off else None, int(cand.group(1)) if cand else None)


def walk_pages(
    op: urllib.request.OpenerDirector,
    start_html: str,
    county: str = "",
    paginate: bool = True,
    max_rows: int | None = None,
) -> list[dict]:
    """Paginate the statewide grid. County-filtered postbacks lose the filter after
    page 1, so callers must set paginate=False for county recovery."""
    collected: list[dict] = []
    seen_pages: set[int] = set()
    html = start_html
    while True:
        pg = current_page(html) or 1
        if pg in seen_pages:
            break
        seen_pages.add(pg)
        rows = parse_grid_rows(html)
        collected.extend(rows)
        print(f"  county={county or 'ALL'} page={pg} rows={len(rows)} total={len(collected)}", flush=True)
        if not paginate:
            break
        if max_rows is not None and len(collected) >= max_rows:
            collected = collected[:max_rows]
            break
        next_target = None
        for m in re.finditer(
            r'href="javascript:__doPostBack\(&#39;([^&]+?)&#39;,\s*&#39;[^&]*?&#39;\)"[^>]*>\s*<span>(\d+)</span>',
            html,
        ):
            if int(m.group(2)) == pg + 1:
                next_target = htmlmod.unescape(m.group(1))
                break
        if not next_target:
            break
        fields = form_fields(html, county)
        fields["__EVENTTARGET"] = next_target
        fields["__EVENTARGUMENT"] = ""
        raw, _ = http(op, fields)
        html = raw.decode("utf-8", "replace")
    return collected


def export_csv(op: urllib.request.OpenerDirector, page: str) -> list[dict]:
    fields = form_fields(page, "")
    fields["ctl00$ContentPlaceHolder1$grdCandidates$ctl00$ctl02$ctl00$ExportToCsvButton"] = " "
    raw, ctype = http(op, fields)
    if "csv" not in ctype.lower() and not raw.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError(f"CSV export did not return CSV: {ctype} {raw[:80]!r}")
    text = raw.decode("utf-8-sig")
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "candidates.csv").write_text(text, encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip().casefold()


def match_key(name: str, race: str, term: str, party: str, filing: str, ballot: str) -> tuple[str, ...]:
    return (
        norm_text(name),
        norm_text(race),
        norm_text(term),
        norm_text(party),
        norm_text(filing),
        norm_text(ballot),
    )


def district_number(text: str) -> str | None:
    m = re.search(r"(?:congressional|legislative)\s+district\s+(\d+)", text, re.I)
    return m.group(1) if m else None


def county_from_district(text: str) -> str | None:
    m = re.search(r"^(.+?)\s+county$", text.strip(), re.I)
    if not m:
        return None
    name = m.group(1).strip()
    if not name or name.casefold() in {"", "the"}:
        return None
    return name.title()


def contest_parts(row: dict) -> tuple[str, str, str]:
    race = row["race"]
    dist = row["district"]
    term = (row.get("term_type") or "").strip()
    vacancy = "" if term.casefold() in {"", "regular"} else term
    num = district_number(dist)
    if num:
        return race, num, vacancy
    if dist.strip().casefold() == "county":
        county = row.get("county") or ""
        return race, county, vacancy
    named = county_from_district(dist)
    if named:
        return race, named, vacancy
    return race, dist, vacancy


def contest_key(office: str, district: str, vacancy: str = "") -> str:
    return f"WA|{office}|{district or ''}|{vacancy or ''}"


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    op = opener()
    raw, _ = http(op)
    start = raw.decode("utf-8", "replace")
    (CACHE / "CandidateList.html").write_text(start, encoding="utf-8")
    offices, cands = page_count_label(start)
    print(f"statewide labels offices={offices} candidates={cands}", flush=True)

    csv_rows = export_csv(op, start)
    print(f"statewide csv rows={len(csv_rows)}", flush=True)
    if len(csv_rows) != 887:
        raise SystemExit(f"expected 887 official CSV rows, got {len(csv_rows)}")

    # Fresh GET for HTML walk (export may have consumed viewstate)
    op = opener()
    raw, _ = http(op)
    start = raw.decode("utf-8", "replace")
    statewide_html_rows = walk_pages(op, start, "")
    print(f"statewide html rows={len(statewide_html_rows)} race_ids={len({r['race_id'] for r in statewide_html_rows if r['race_id']})}", flush=True)

    # County recovery: District == County rows from each county-filtered grid
    county_hits: dict[tuple[str, ...], set[str]] = defaultdict(set)
    county_rows_by_county: dict[str, list[dict]] = {}
    for code, name in COUNTIES:
        op = opener()
        raw, _ = http(op)
        page = raw.decode("utf-8", "replace")
        fields = form_fields(page, code)
        fields["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$ddlCounty"
        fields["__EVENTARGUMENT"] = ""
        raw, _ = http(op, fields)
        page = raw.decode("utf-8", "replace")
        off, n = page_count_label(page)
        print(f"filter {name} ({code}) offices={off} candidates={n}", flush=True)
        # Page 1 of the county postback is the only filtered page that stays
        # scoped. Further pager postbacks revert to the statewide grid.
        rows = walk_pages(op, page, code, paginate=False)
        county_rows_by_county[name] = rows
        for r in rows:
            if r["district"].strip().casefold() != "county":
                continue
            key = match_key(r["candidate_name"], r["race"], r["term_type"], "", "", "")
            county_hits[key].add(name)
        time.sleep(0.15)

    recovered: dict[tuple[str, ...], str] = {}
    ambiguous = 0
    for key, names in county_hits.items():
        if len(names) == 1:
            recovered[key] = next(iter(names))
        else:
            ambiguous += 1
            print(f"AMBIGUOUS county {key} -> {sorted(names)}", flush=True)
    print(f"county recovery keys={len(recovered)} ambiguous={ambiguous}", flush=True)

    name_to_ids: dict[tuple[str, str], dict] = {}
    for r in statewide_html_rows:
        name_to_ids[(norm_text(r["candidate_name"]), norm_text(r["race"]))] = r

    out: list[dict] = []
    missing_county = 0
    for raw_row in csv_rows:
        name = (raw_row.get("Name") or "").strip()
        race = (raw_row.get("Race") or "").strip()
        district = (raw_row.get("District") or "").strip()
        dtype = (raw_row.get("District Type") or "").strip()
        term = (raw_row.get("Term Type") or "").strip()
        length = (raw_row.get("Term Length") or "").strip()
        party = (raw_row.get("Party Preference") or "").strip()
        status = (raw_row.get("Status") or "").strip()
        filing = (raw_row.get("Filing Date") or "").strip()
        ballot = (raw_row.get("Ballot Order") or "").strip()
        county = None
        if district.casefold() == "county":
            key = match_key(name, race, term, "", "", "")
            county = recovered.get(key)
            if not county:
                hits = {n for k, nset in county_hits.items() if k[:2] == key[:2] for n in nset}
                if len(hits) == 1:
                    county = next(iter(hits))
                elif not hits:
                    # Only King (153) exceeds the 100-row page. Leftover
                    # District=County rows are the King page-2 remainder.
                    county = "King"
                    print(f"KING remainder {name!r} {race!r} {term!r}", flush=True)
                else:
                    missing_county += 1
                    print(f"NO COUNTY {name!r} {race!r} {term!r} hits={sorted(hits)}", flush=True)
        ids = name_to_ids.get((norm_text(name), norm_text(race)), {})
        rec = {
            "state": "WA",
            "district_type": dtype,
            "district_raw": district,
            "race": race,
            "office": race,
            "term_type": term or None,
            "term_length": int(length) if length.isdigit() else (length or None),
            "candidate_name": name,
            "party": party or None,
            "status": status or None,
            "filing_date": filing or None,
            "ballot_order": int(ballot) if ballot.isdigit() else None,
            "county": county,
            "race_id": ids.get("race_id"),
            "candidate_id": ids.get("candidate_id"),
            "list_kind": "general_official",
            "election_id": int(ELECTION_ID),
            "source_url": LIST_URL,
            "retrieved_at": RETRIEVED,
        }
        office, dist, vacancy = contest_parts(
            {
                "race": race,
                "district": district,
                "term_type": term,
                "county": county,
            }
        )
        rec["office"] = office
        rec["district"] = dist or None
        rec["contest_key"] = contest_key(office, dist, vacancy)
        out.append(rec)

    keys = {r["contest_key"] for r in out}
    print(f"wrote candidates={len(out)} contest_keys={len(keys)} missing_county={missing_county}", flush=True)
    print("district_type", Counter(r["district_type"] for r in out))
    print("sample keys", list(sorted(keys))[:12])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    house = [r for r in out if "u.s. representative" in (r.get("race") or "").casefold()]
    senate = [r for r in out if (r.get("race") or "").casefold() == "state senator"]
    house_rep = [r for r in out if (r.get("race") or "").casefold().startswith("state representative")]
    summary = {
        "row_count": len(out),
        "contest_key_count": len(keys),
        "us_house": len(house),
        "us_house_districts": sorted({int(r["district"]) for r in house if str(r.get("district") or "").isdigit()}),
        "state_senator": len(senate),
        "state_representative": len(house_rep),
        "countywide_recovered": sum(1 for r in out if r.get("county") and (r.get("district_raw") or "").casefold() == "county"),
        "source_url": LIST_URL,
        "retrieved_at": RETRIEVED,
        "list_kind": "general_official",
        "election_id": int(ELECTION_ID),
        "official_office_count_label": offices,
        "official_candidate_count_label": cands,
        "streets_omitted": True,
    }
    (OUT_DIR / "candidate-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stub = json.loads(STUB.read_text(encoding="utf-8"))
    donors = ((stub.get("state_filings") or {}).get("donors") or {}).copy()
    election = stub.setdefault("election", {})
    election["note"] = (
        "Official VoteWA GENERAL 2026 candidate list (election 899), Clerk/LIS federal votes, "
        "and PDC Schedule A donors. Donor lists are not sold."
    )
    stub["candidates_path"] = "/data/wa/candidates.json"
    stub["candidate_summary_path"] = "/data/wa/candidate-summary.json"
    stub.setdefault("votes_path", "/data/wa/votes.json")
    sources = stub.setdefault("sources", [])
    if not any((s.get("url") == LIST_URL) for s in sources):
        sources.append({"url": LIST_URL, "retrieved_at": RETRIEVED, "note": "VoteWA CandidateList GENERAL 2026 e=899"})
    if donors:
        stub["state_filings"]["donors"] = donors
    STUB.write_text(json.dumps(stub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("merged wa.json donors.status", donors.get("status"), "candidates_path", stub.get("candidates_path"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
