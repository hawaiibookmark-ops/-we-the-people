#!/usr/bin/env python3
"""Fixture test for scripts/prepare_pages_export.py (no Next build required)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREPARE = ROOT / "scripts" / "prepare_pages_export.py"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_prepare(out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PREPARE), str(out)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )


def assert_ok(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"TEST FAIL: {msg}")


def test_dual_publish() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        write(
            out / "index.html",
            '<html><body><h1>We The People</h1><script src="/-we-the-people/_next/static/x.js"></script></body></html>',
        )
        write(out / "lookup" / "index.html", "<html><body>lookup</body></html>")
        write(out / "_next" / "static" / "x.js", "console.log(1)")
        write(out / "data" / "meta.json", "{}")
        (out / ".nojekyll").touch()

        result = run_prepare(out)
        assert_ok(result.returncode == 0, result.stderr or result.stdout)
        nested = out / "-we-the-people"
        assert_ok((nested / "index.html").is_file(), "nested hub missing")
        assert_ok("We The People" in (nested / "index.html").read_text(encoding="utf-8"), "nested hub text")
        assert_ok((nested / "_next" / "static" / "x.js").is_file(), "nested assets missing")
        assert_ok((nested / "lookup" / "index.html").is_file(), "nested lookup missing")
        assert_ok((nested / "data" / "meta.json").is_file(), "nested data missing")
        assert_ok(not (out / "CNAME").exists(), "CNAME must stay unpublished")


def test_refuses_github_io_asset_origin() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        write(
            out / "index.html",
            '<html><body><h1>We The People</h1>'
            '<script src="https://hawaiibookmark-ops.github.io/-we-the-people/_next/static/x.js"></script>'
            "</body></html>",
        )
        write(out / "lookup" / "index.html", "<html></html>")
        write(out / "_next" / "x.js", "1")
        write(out / "data" / "meta.json", "{}")
        result = run_prepare(out)
        assert_ok(result.returncode != 0, "should refuse github.io asset origin")
        assert_ok("github.io origin" in result.stderr, result.stderr)


def test_refuses_missing_root_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        write(out / "-we-the-people" / "index.html", "<html><body>We The People</body></html>")
        result = run_prepare(out)
        assert_ok(result.returncode != 0, "should refuse empty apex root")
        assert_ok("index.html missing" in result.stderr, result.stderr)


def main() -> None:
    test_dual_publish()
    test_refuses_github_io_asset_origin()
    test_refuses_missing_root_index()
    print("OK prepare_pages_export tests")


if __name__ == "__main__":
    main()
