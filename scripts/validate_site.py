"""Validate and assemble the public presentation site; never package original replays."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit, unquote


ROOT = Path(__file__).resolve().parents[1]
BLOCKED = {".mp4", ".mov", ".webm", ".avi", ".csv", ".pkl", ".npy", ".npz", ".zip", ".xosc", ".xml", ".log"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()
        self.images = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            assert a["id"] not in self.ids, f"Duplicate element ID: {a['id']}"
            self.ids.add(a["id"])
        for key in ("src", "href"):
            if a.get(key):
                self.links.append(a[key])
        if tag == "img":
            assert "alt" in a, "Image is missing alternative text"
            self.images += 1
        assert tag not in {"video", "source"}, "Only GIF previews may be published"


def validate():
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "{{" not in page, "Unresolved build placeholder"
    for pattern in (r"sk-or-v1-", r"gh[pousr]_[A-Za-z0-9]", r"\bR0[0-9]\b", r"Request family kept", r"All 22 models", r"600 veh/h", r"tokens in /", r"HD video"):
        assert not re.search(pattern, page, re.I), f"Unwanted public content: {pattern}"
    p = Page()
    p.feed(page)
    for link in p.links:
        u = urlsplit(link)
        if u.scheme or u.netloc:
            continue
        if u.path:
            target = (ROOT / unquote(u.path)).resolve()
            assert target.is_relative_to(ROOT), f"Asset escapes site root: {link}"
            assert target.is_file(), f"Missing local asset: {link}"
        elif u.fragment:
            assert u.fragment in p.ids, f"Broken section link: {link}"
    files = [ROOT / "index.html", *[f for f in (ROOT / "static").rglob("*") if f.is_file()]]
    for f in files:
        assert f.suffix.lower() not in BLOCKED, f"Original replay/video in public tree: {f.name}"
        if f.suffix.lower() in {".json", ".js", ".html", ".css"}:
            s = f.read_text(encoding="utf-8")
            assert not re.search(r"sk-or-v1-|gh[pousr]_[A-Za-z0-9]{20}", s), "Credential-like content in site"
    d = json.loads((ROOT / "static/data/review.json").read_text(encoding="utf-8"))
    assert "bundle" not in d, "Internal run metadata is not public content"
    for c in d["cases"]:
        assert not {"ego_path", "partner_path", "trajectory", "trajectories", "source", "run"}.intersection(c), "Recorded paths in public case metadata"
    print(f"PASS: {p.images} images, {len(files)} public files; local links resolve; original replays/videos and credentials excluded.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-dir")
    args = ap.parse_args()
    validate()
    if args.build_dir:
        dest = (ROOT / args.build_dir).resolve()
        assert dest.is_relative_to(ROOT) and dest != ROOT, "Build must stay inside the site checkout"
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("index.html", ".nojekyll", "MEDIA_NOTICE.md"):
            shutil.copy2(ROOT / name, dest / name)
        shutil.copytree(ROOT / "static", dest / "static", dirs_exist_ok=True)
        for f in dest.rglob("*"):
            if f.is_file():
                assert f.suffix.lower() not in BLOCKED, "Unsafe cached build artifact"
        print("Public site assembled.")


if __name__ == "__main__":
    main()
