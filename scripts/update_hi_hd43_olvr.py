#!/usr/bin/env python3
"""Apply official OLVR Dist 43 Republican status updates (elid=94).

MEDEIROS, Sheila / SHEILA MEDEIROS: Elected After Primary → In General.
SOUZA, Kanani / KRISTEN K. SOUZA: In Primary → In General.
Do not confuse with OHA At-Large Trustee SOUZA, Keoni / JUSTIN PATRICK KEONI SOUZA.
Certified 2026 Primary summary lists both Republicans at 842 votes (tie).
Does not rewrite Dist 18, OHA Keoni, CSC, FEC, or votes. Streets/email/phone omitted.
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
RETRIEVED = "2026-09-11T18:05:04.125Z"
OLVR = "https://olvr.hawaii.gov/Controls/CandidateFiling.aspx?elid=94"
UA = "WeThePeople-CivicBot/1.0"
PACKAGE_DIRS = [
    Path("/workspace/wtp-live-data/run-2026-09-11-hi08-routine"),
    Path("/tmp/wtp-live-data/run-2026-09-11-hi08-routine"),
]
HD43 = "State Representative, Dist 43"
FROZEN = {
    "csc-donors.json": None,
    "donors.json": None,
    "hawaii-votes.json": None,
    "congress-votes.json": None,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nominee(name: str, legal: str) -> dict:
    return {
        "office": HD43,
        "kind": "state_house",
        "district": "43",
        "party": "Republican Party",
        "party_code": "R",
        "name": name,
        "legal_name": legal,
        "primary_votes": 842,
        "field": "general_nominee",
        "status": "In General",
        "source_url": OLVR,
        "retrieved_at": RETRIEVED,
    }


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
    before = {name: sha256(OUT / name) for name in FROZEN}
    packaged = None
    for d in PACKAGE_DIRS:
        p = d / "hawaii.json"
        if p.is_file():
            packaged = json.loads(p.read_text(encoding="utf-8"))
            print(f"using packaged {p}", flush=True)
            break

    hi = json.loads((OUT / "hawaii.json").read_text(encoding="utf-8"))
    sd18_before = json.loads(json.dumps(hi["nominees"].get("State Senator, Dist 18 Vacancy")))
    hd18_before = json.loads(json.dumps(hi["nominees"].get("State Representative, Dist 18")))
    oha_keoni_before = json.loads(
        json.dumps(
            [
                n
                for n in (hi.get("nonpartisan_primary") or {}).get("At-Large Trustee") or []
                if n.get("name") == "SOUZA, Keoni"
            ]
        )
    )

    if packaged:
        hd43 = (packaged.get("nominees") or {}).get(HD43) or []
        names = {(n.get("name"), n.get("status"), n.get("field")) for n in hd43}
        need = {
            ("MEDEIROS, Sheila", "In General", "general_nominee"),
            ("SOUZA, Kanani", "In General", "general_nominee"),
        }
        if names != need:
            raise SystemExit(f"packaged Dist 43 not both In General: {names}")
        hi["nominees"][HD43] = hd43
    else:
        rows = fetch_olvr_csv()
        if len(rows) != 415:
            raise SystemExit(f"official OLVR count {len(rows)} != 415")
        hd43_rows = [r for r in rows if (r.get("Contests") or "") == "STATE REPRESENTATIVE, DIST 43"]
        got = {
            ((r.get("BallotName") or "").strip(), (r.get("Party") or "").strip(), (r.get("Status") or "").strip())
            for r in hd43_rows
        }
        if got != {("MEDEIROS, Sheila", "REPUBLICAN", "In General"), ("SOUZA, Kanani", "REPUBLICAN", "In General")}:
            raise SystemExit(f"official OLVR Dist 43 unexpected: {got}")
        if any((r.get("BallotName") or "").strip() == "SOUZA, Keoni" for r in hd43_rows):
            raise SystemExit("refusing to put OHA SOUZA, Keoni on Dist 43")
        hi["nominees"][HD43] = [
            nominee("MEDEIROS, Sheila", "SHEILA MEDEIROS"),
            nominee("SOUZA, Kanani", "KRISTEN K. SOUZA"),
        ]

    if hi["nominees"].get("State Senator, Dist 18 Vacancy") != sd18_before:
        raise SystemExit("refusing to change Dist 18 Senate Vacancy")
    if hi["nominees"].get("State Representative, Dist 18") != hd18_before:
        raise SystemExit("refusing to change Dist 18 House")
    oha_keoni_after = [
        n
        for n in (hi.get("nonpartisan_primary") or {}).get("At-Large Trustee") or []
        if n.get("name") == "SOUZA, Keoni"
    ]
    if oha_keoni_after != oha_keoni_before:
        raise SystemExit("refusing to change OHA At-Large Trustee SOUZA, Keoni")
    if any(n.get("name") == "SOUZA, Keoni" for n in hi["nominees"].get(HD43) or []):
        raise SystemExit("refusing to put OHA SOUZA, Keoni on Dist 43")

    (OUT / "hawaii.json").write_text(json.dumps(hi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    after = {name: sha256(OUT / name) for name in before}
    if after != before:
        raise SystemExit(f"refusing wipe { {k: (before[k], after[k]) for k in before if before[k] != after[k]} }")
    print(
        json.dumps(
            {
                "hd43": ["MEDEIROS, Sheila", "SOUZA, Kanani"],
                "status": "In General",
                "retrieved_at": RETRIEVED,
                "olvr": OLVR,
                "olvr_count": 415,
                "dist18_unchanged": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
