#!/usr/bin/env python3
"""Dual-publish the Next export for GitHub project Pages + custom-domain apex.

Custom domains serve the artifact at `/`. Project github.io serves the same
artifact under `/-we-the-people/`. One tree cannot 404 either host:

  out/index.html                  → getwethepeople.com/
  out/lookup/, out/data/, out/_next
  out/-we-the-people/index.html   → getwethepeople.com/-we-the-people/
                                    (and github.io 301s that preserve the repo path)
  out/-we-the-people/_next        → same-origin assets when HTML uses
                                    assetPrefix `/-we-the-people`

Never writes a CNAME. Attaching the domain is a repo-admin Settings step
and must wait until this layout is live.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_PREFIX = "-we-the-people"
HUB_MARK = "We The People"
ASSET_MARK = "/-we-the-people/_next"
FORBIDDEN_ASSET_ORIGIN = "https://hawaiibookmark-ops.github.io/-we-the-people/"


def out_dir() -> Path:
    raw = os.environ.get("WTP_EXPORT_DIR") or (sys.argv[1] if len(sys.argv) > 1 else "out")
    return Path(raw).resolve()


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def dual_publish(root: Path) -> Path:
    dest = root / REPO_PREFIX
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for item in root.iterdir():
        if item.name == REPO_PREFIX:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=False)
        else:
            shutil.copy2(item, target)
    (dest / ".nojekyll").touch()
    return dest


def verify(root: Path) -> None:
    index = root / "index.html"
    if not index.is_file():
        fail("out/index.html missing — custom-domain apex / would 404")
    html = read(index)
    if HUB_MARK not in html:
        fail("out/index.html is not the We The People hub")
    if ASSET_MARK not in html:
        fail(
            "out/index.html does not reference /-we-the-people/_next "
            "(build with WTP_PAGES_EXPORT=1 or GITHUB_ACTIONS)"
        )
    if FORBIDDEN_ASSET_ORIGIN in html:
        fail(
            "out/index.html still loads assets from the github.io origin; "
            "that origin 301s to apex after the custom domain is attached"
        )
    if (root / "CNAME").exists():
        fail("out/CNAME must not be published (github.io would 301 before apex is proven)")

    lookup = root / "lookup" / "index.html"
    if not lookup.is_file():
        fail("out/lookup/index.html missing")
    if not (root / "data").is_dir():
        fail("out/data/ missing")
    if not (root / "_next").is_dir():
        fail("out/_next/ missing")

    nested = root / REPO_PREFIX
    nested_index = nested / "index.html"
    if not nested_index.is_file():
        fail("out/-we-the-people/index.html missing — dual publish failed")
    if HUB_MARK not in read(nested_index):
        fail("out/-we-the-people/index.html is not the We The People hub")
    if not (nested / "_next").is_dir():
        fail("out/-we-the-people/_next/ missing — apex assetPrefix would 404")
    if not (nested / "lookup" / "index.html").is_file():
        fail("out/-we-the-people/lookup/index.html missing")
    if not (nested / "data").is_dir():
        fail("out/-we-the-people/data/ missing")


def main() -> None:
    root = out_dir()
    if not root.is_dir():
        fail(f"export dir not found: {root}")
    (root / ".nojekyll").touch()
    dual_publish(root)
    verify(root)
    print("OK pages export layout")
    print(f"  {root / 'index.html'}  (custom-domain apex /)")
    print(f"  {root / 'lookup' / 'index.html'}")
    print(f"  {root / 'data'}")
    print(f"  {root / '_next'}  (github.io project-path assets)")
    print(f"  {root / REPO_PREFIX / 'index.html'}  (/-we-the-people/ on either host)")
    print(f"  {root / REPO_PREFIX / '_next'}  (apex same-origin assets)")
    print("  no CNAME")


if __name__ == "__main__":
    main()
