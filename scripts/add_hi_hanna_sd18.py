#!/usr/bin/env python3
"""Add official OLVR HANNA, Max G. (N) to SD18 Vacancy In General.

Source: Hawaii OLVR Candidate Report elid=94. Dist 18 In General is Bass (D),
Kitashima (R), Hanna (N). CUADRA remains Filed and is not promoted.
Does not rewrite CSC, FEC, or congress votes. Streets omitted.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data"
RETRIEVED = "2026-09-07T18:10:27Z"
OLVR = "https://olvr.hawaii.gov/Controls/CandidateFiling.aspx?elid=94"
UA = "WeThePeople-CivicBot/1.0"
HANNA = {
    "office": "State Senator, Dist 18 Vacancy",
    "kind": "state_senate",
    "district": "18",
    "party": "Nonpartisan",
    "party_code": "N",
    "name": "HANNA, Max G.",
    "legal_name": "MAX G. HANNA",
    "field": "general_nominee",
    "status": "In General",
    "source_url": OLVR,
    "retrieved_at": RETRIEVED,
}
FROZEN = {
    "csc-donors.json": "224c7ec6e7a1917ae9ba548d12012125deddace8728d3bbf3af1f6269cd84984",
    "donors.json": "0da3ef63f07e81cb9c1f67d685546e06b25c66d1dfd06794e2448e799abd8135",
    "congress-votes.json": None,
}
PACKAGE_DIRS = [
    Path("/workspace/wtp-live-data/run-2026-09-07-hi08-routine"),
    Path("/tmp/wtp-live-data/run-2026-09-07-hi08-routine"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_olvr_csv() -> list[dict]:
    req = urllib.request.Request(OLVR, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    def hid(name: str) -> str:
        m = re.search(rf'name="{re.escape(name)}" id="[^"]*" value="([^"]*)"', html)
        if not m:
            m = re.search(rf'id="{re.escape(name)}" value="([^"]*)"', html)
        return m.group(1) if m else ""

    fields = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": hid("__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": hid("__VIEWSTATEGENERATOR"),
        "__VIEWSTATEENCRYPTED": "",
        "__EVENTVALIDATION": hid("__EVENTVALIDATION"),
        "ctl00$cphFooter$ddlElection": "94",
        "ctl00$cphFooter$rdgSearch$ctl00$ctl02$ctl00$ExportToCsvButton": "",
    }
    post = urllib.request.Request(
        OLVR,
        data=urllib.parse.urlencode(fields).encode(),
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": OLVR,
            "Accept": "text/csv,*/*",
        },
        method="POST",
    )
    with urllib.request.urlopen(post, timeout=90) as resp:
        body = resp.read().decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(body)))


def main() -> int:
    before = {name: sha256(OUT / name) for name in ("csc-donors.json", "donors.json", "congress-votes.json")}
    if before["csc-donors.json"] != FROZEN["csc-donors.json"]:
        raise SystemExit("refusing to change CSC while adding Hanna")
    if before["donors.json"] != FROZEN["donors.json"]:
        raise SystemExit("refusing to change FEC donors.json")

    packaged = None
    for d in PACKAGE_DIRS:
        p = d / "hawaii.json"
        if p.is_file():
            packaged = json.loads(p.read_text(encoding="utf-8"))
            print(f"using packaged {p}", flush=True)
            break
    if packaged:
        sd = (packaged.get("nominees") or {}).get("State Senator, Dist 18 Vacancy") or []
        hanna = next((n for n in sd if n.get("name") == "HANNA, Max G."), None)
        if not hanna or hanna.get("status") != "In General":
            raise SystemExit("packaged hawaii.json missing Hanna In General")
        hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
        hi["nominees"]["State Senator, Dist 18 Vacancy"] = sd
    else:
        rows = fetch_olvr_csv()
        vac = [r for r in rows if (r.get("Contests") or "").upper() == "STATE SENATOR, DIST 18 VACANCY"]
        in_gen = {(r.get("BallotName") or "").strip(): (r.get("Party") or "", r.get("Status") or "") for r in vac}
        if in_gen.get("HANNA, Max G.") != ("NONPARTISAN", "In General"):
            raise SystemExit(f"official OLVR Hanna not In General: {in_gen.get('HANNA, Max G.')}")
        if in_gen.get("BASS, Danielle Maliekekai")[1] != "In General":
            raise SystemExit("official OLVR Bass not In General")
        if in_gen.get("KITASHIMA, Kelly Puamailani")[1] != "In General":
            raise SystemExit("official OLVR Kitashima not In General")
        if in_gen.get("CUADRA, Ku L. (Bobby)", ("", ""))[1] == "In General":
            raise SystemExit("refusing to invent CUADRA as In General")
        hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
        sd = list((hi.get("nominees") or {}).get("State Senator, Dist 18 Vacancy") or [])
        sd = [n for n in sd if n.get("name") != "HANNA, Max G."]
        sd.append(HANNA)
        hi["nominees"]["State Senator, Dist 18 Vacancy"] = sd

    (OUT / "hawaii.json").write_text(json.dumps(hi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    after = {name: sha256(OUT / name) for name in before}
    if after != before:
        raise SystemExit(f"refusing wipe { {k: (before[k], after[k]) for k in before if before[k] != after[k]} }")
    print(json.dumps({"hanna": "In General", "retrieved_at": RETRIEVED, "olvr": OLVR, "csc_fec_votes_unchanged": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
